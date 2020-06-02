---
layout: post
title:  "Flink提交批任务"
categories: Flink
tags: Flink 大数据
author: Victor
---

* content
{:toc}

#### 前言  
了解一个框架，得首先了解它的执行过程。而源码追溯就是一个很好的学习方法，通过一层层的引用查看，可以很好的理解Flink在提交任务过程中做了什么。从经典WordCount程序出发，学习Flink。  

#### 解析可执行环境  
最经典的计算示例莫过于WorldCount，Flink中的示例提交方式很简单：bin/flink run examples/batch/WordCount.jar。即来到Flink的根目录，命令行输入以上指令便可进行简单的单词统计功能。打开源代码，可以看到bin/flink是一个shell脚本，用于预加载环境并启动Java程序。  
<!-- more -->
```
#代表bin/flink文件路径
target="$0"
......

#获取bin目录的绝对路径
bin=`dirname "$target"`

#加载默认的系统环境设置
. "$bin"/config.sh
#获取用户名
if [ "$FLINK_IDENT_STRING" = "" ]; then
        FLINK_IDENT_STRING="$USER"
fi

CC_CLASSPATH=`constructFlinkClassPath`
#指定日志配置文件
log=$FLINK_LOG_DIR/flink-$FLINK_IDENT_STRING-client-$HOSTNAME.log
log_setting=(-Dlog.file="$log" -Dlog4j.configuration=file:"$FLINK_CONF_DIR"/log4j-cli.properties -Dlog4j.configurationFile=file:"$FLINK_CONF_DIR"/log4j-cli.properties -Dlogback.configurationFile=file:"$FLINK_CONF_DIR"/logback.xml)

#拼接默认的JVM启动参数
FLINK_ENV_JAVA_OPTS="${FLINK_ENV_JAVA_OPTS} ${FLINK_ENV_JAVA_OPTS_CLI}"

#加Hadoop系统环境变量，启动flink client提交程序并指定Main Class
exec $JAVA_RUN $JVM_ARGS $FLINK_ENV_JAVA_OPTS "${log_setting[@]}" -classpath "`manglePathList "$CC_CLASSPATH:$INTERNAL_HADOOP_CLASSPATHS"`" org.apache.flink.client.cli.CliFrontend "$@"
```  
接下来来看org.apache.flink.client.cli.CliFrontend这个类
```
public static void main(final String[] args) {
    //日志打印出当前执行环境的基本信息
	EnvironmentInformation.logEnvironmentInfo(LOG, "Command Line Client", args);
	//找到配置目录
	final String configurationDirectory = getConfigurationDirectoryFromEnv();
	//加载配置目录文件
	final Configuration configuration = GlobalConfiguration.loadConfiguration(configurationDirectory);
	//加载三种CustomCommandLine实例
	final List<CustomCommandLine> customCommandLines = loadCustomCommandLines(
		configuration,
		configurationDirectory);
	try {
		final CliFrontend cli = new CliFrontend(
			configuration,
			customCommandLines);
		SecurityUtils.install(new SecurityConfiguration(cli.configuration));
		//根据命令行传递过来的参数做后续动作
		int retCode = SecurityUtils.getInstalledContext()
				.runSecured(() -> cli.parseParameters(args));
		System.exit(retCode);
	}
	catch (Throwable t) {
		final Throwable strippedThrowable = ExceptionUtils.stripException(t, UndeclaredThrowableException.class);
		LOG.error("Fatal error while running command line interface.", strippedThrowable);
		strippedThrowable.printStackTrace();
		System.exit(31);
	}
}
```
上面cli.parseParameter解析参数，触发action。  
```
public int parseParameters(String[] args) {
    ...省略...
    //获取命令行第一个参数，示例中的值是run
	String action = args[0];
	//截取除了第一个参数外的其他参数
	final String[] params = Arrays.copyOfRange(args, 1, args.length);

	switch (action) {
		//执行run操作
		case ACTION_RUN:
			run(params);
			return 0;
		//执行run application
		case ACTION_RUN_APPLICATION:
			runApplication(params);
			return 0;
	    //展示可用参数列表
		case ACTION_LIST:
			list(params);
			return 0;
		//展示flink基础信息
		case ACTION_INFO:
			info(params);
			return 0;
		//取消执行任务
		case ACTION_CANCEL:
			cancel(params);
			return 0;
		//停止任务
		case ACTION_STOP:
			stop(params);
			return 0;
		//触发checkpoint操作
		case ACTION_SAVEPOINT:
			savepoint(params);
			return 0;
		...省略...
	}
}
```  
紧接着示例开始执行run(params)方法，根据传入的examples/batch/WordCount.jar来寻找该类的具体路径、依赖的执行环境和jar包，最后通过ClientUtils.executeProgram方法来创建加载全局执行上线文并唤醒WordCount的main方法。  
```
public static void executeProgram(
		PipelineExecutorServiceLoader executorServiceLoader,
		Configuration configuration,
		PackagedProgram program,
		boolean enforceSingleJobExecution,
		boolean suppressSysout) throws ProgramInvocationException {
	    ...省略...
		ContextEnvironment.setAsContext(
			executorServiceLoader,
			configuration,
			userCodeClassLoader,
			enforceSingleJobExecution,
			suppressSysout);

		StreamContextEnvironment.setAsContext(
			executorServiceLoader,
			configuration,
			userCodeClassLoader,
			enforceSingleJobExecution,
			suppressSysout);
		...省略...
		program.invokeInteractiveModeForExecution();
		...省略...
}
public void invokeInteractiveModeForExecution() throws ProgramInvocationException {
		callMainMethod(mainClass, args);
}
```
#### WordCount任务提交  
终于到了WordCount这个实际业务类，该类实现了简单的单词个数统计功能。
```
public static void main(String[] args) throws Exception {  
	...省略...
	//初始化flink任务可执行环境
	final ExecutionEnvironment env = ExecutionEnvironment.getExecutionEnvironment();
	...省略...
	DataSet<String> text = null;
	//获取默认单词源并转换为DataSet类型
	if (params.has("input")) {
		...省略...
	} else {
		...省略...
		text = WordCountData.getDefaultTextLineDataSet(env);
	}
	//建立文本切分规则，根据算子得出计算逻辑
	DataSet<Tuple2<String, Integer>> counts =
			// split up the lines in pairs (2-tuples) containing: (word,1)
			text.flatMap(new Tokenizer())
			// group by the tuple field "0" and sum up tuple field "1"
			.groupBy(0)
			.sum(1);

	//异步提交输出结果
	if (params.has("output")) {
		counts.writeAsCsv(params.get("output"), "\n", " ");
		//这一步才会真正的执行并提交任务
		env.execute("WordCount Example");
	} else {
		counts.print();
	}
}
```  
这里Flink的提交具体是在ExecutionEnvironment.executeAsync方法中。  
```
public JobClient executeAsync(String jobName) throws Exception {
	//创建执行计划
	final Plan plan = createProgramPlan(jobName);
	//这里的executorServiceLoader实际上是DefaultExecutorServiceLoader INSTANCE = new DefaultExecutorServiceLoader()
	final PipelineExecutorFactory executorFactory =
		executorServiceLoader.getExecutorFactory(configuration);
	...省略...
	//提交执行计划
	CompletableFuture<JobClient> jobClientFuture = executorFactory
		.getExecutor(configuration)
		.execute(plan, configuration);

	try {
		JobClient jobClient = jobClientFuture.get();
		//监控任务状态信息
		jobListeners.forEach(jobListener -> jobListener.onJobSubmitted(jobClient, null));
		return jobClient;
	} catch (Throwable t) {
		jobListeners.forEach(jobListener -> jobListener.onJobSubmitted(null, t));
		ExceptionUtils.rethrow(t);

		return null;
	}
}
```  
创建执行计划的具体实现在PlanGenerator.generate()方法中，这里OperatorTranslation的translate方法至关重要，将每个sink构造成GenericDataSinkBase，这里GenericDataSinkBase间接的实现了accept方法。
```
public Plan generate() {
	//构造Plan对象，并带有GenericDataSinkBase类型的sink
	final Plan plan = createPlan();
	//解析依赖DAG执行计划
	registerGenericTypeInfoIfConfigured(plan);
	//完成自动类型注册之后，将缓存文件注册到Plan对象上：
	registerCachedFiles(plan);

	logTypeRegistrationDetails();
	return plan;
}
```
接下来便是DAG的解析过程，这里是在PlanGenerator.registerGenericTypeInfoIfConfigured方法触发，经Plan.accept处理再到GenericDataSinkBase.accept方法完成前后依赖关系。
```
@Override
public void accept(Visitor<Operator<?>> visitor) {
	for (GenericDataSinkBase<?> sink : this.sinks) {
		sink.accept(visitor);
	}
}
//深度优先遍历，递归搜索算子依赖到single input
@Override
public void accept(Visitor<Operator<?>> visitor) {
	boolean descend = visitor.preVisit(this);
	if (descend) {
		this.input.accept(visitor);
		visitor.postVisit(this);
	}
}
```
#### 计划优化  
这里的计划优化部分起始于ExecutionEnvironment.executeAsync方法，当得到Plan实例之后，从配置文件加载得到指定的执行器，继而执行execute方法。
```
public JobClient executeAsync(String jobName) throws Exception {

	final Plan plan = createProgramPlan(jobName);
	//这里的executorServiceLoader是DefaultExecutorServiceLoader实例
	final PipelineExecutorFactory executorFactory =
		executorServiceLoader.getExecutorFactory(configuration);
    ...省略...
    //示例中获得LocalExecutor作为Executor，进而执行execute方法
	CompletableFuture<JobClient> jobClientFuture = executorFactory
		.getExecutor(configuration)
		.execute(plan, configuration);
	...省略...
}
```
下面LocalExecutor类的execute方法会依次调用LocalExecutor.getJobGraph->PipelineExecutorUtils.getJobGraph->FlinkPipelineTranslationUtil.getJobGraph->PlanTranslator.translateToJobGraph->PlanTranslator.compilePlan。
```
//LocalExecutor类
@Override
public CompletableFuture<JobClient> execute(Pipeline pipeline, Configuration configuration) throws Exception {
	...省略...
	//这里生成JobGraph，优化Plan中的依赖关系。这里的pipeline在示例中就是Plan实例
	final JobGraph jobGraph = getJobGraph(pipeline, effectiveConfig);
	return PerJobMiniClusterFactory.createWithFactory(effectiveConfig, miniClusterFactory).submitJob(jobGraph);
}
//FlinkPipelineTranslationUtil类
public static JobGraph getJobGraph(Pipeline pipeline,Configuration optimizerConfiguration,int defaultParallelism) {
	//这里示例返回的类是PlanTranslator
	FlinkPipelineTranslator pipelineTranslator = getPipelineTranslator(pipeline);
	//实际上是调用PlanTranslator.translateToJobGraph
	return pipelineTranslator.translateToJobGraph(pipeline,
			optimizerConfiguration,
			defaultParallelism);
}
//PlanTranslator类
private JobGraph compilePlan(Plan plan, Configuration optimizerConfiguration) {
	Optimizer optimizer = new Optimizer(new DataStatistics(), optimizerConfiguration);
	//构造OptimizedPlan
	OptimizedPlan optimizedPlan = optimizer.compile(plan);

	JobGraphGenerator jobGraphGenerator = new JobGraphGenerator(optimizerConfiguration);
	//用LinkedHashMap记录链式关系，返回最终的JobGraph
	return jobGraphGenerator.compileJobGraph(optimizedPlan, plan.getJobId());
}
```  
最后，通过PerJobMiniClusterFactory提交Job，也就是如下代码演示的过程。
```
public CompletableFuture<JobClient> submitJob(JobGraph jobGraph) throws Exception {
	MiniClusterConfiguration miniClusterConfig = getMiniClusterConfig(jobGraph.getMaximumParallelism());
	MiniCluster miniCluster = miniClusterFactory.apply(miniClusterConfig);
	miniCluster.start();

	return miniCluster
		.submitJob(jobGraph)
		.thenApply(result -> new PerJobMiniClusterJobClient(result.getJobID(), miniCluster))
		.whenComplete((ignored, throwable) -> {
			if (throwable != null) {
				// We failed to create the JobClient and must shutdown to ensure cleanup.
				shutDownCluster(miniCluster);
			}
		})
		.thenApply(Function.identity());
}
```  

WorldCount批示例代码追踪就先记录到这里，初次记录还有些许不明了的地方，希望在实践中加以验证！  
