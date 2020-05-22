---
layout: post
title:  "Datax源码分析二"
categories: Datax
tags: datax 源代码
author: Victor
---

* content
{:toc}

接着上一节......
做好了切分工作，下一步当然就是对对应的各个任务进行任务托管和监控：schedule，post，postHandle，invokeHooks。
schedule首先完成的工作是把上一步reader和writer split的结果整合到具体的taskGroupContainer中。
```
int channelsPerTaskGroup = this.configuration.getInt(
        CoreConstant.DATAX_CORE_CONTAINER_TASKGROUP_CHANNEL, 5);
int taskNumber = this.configuration.getList(
        CoreConstant.DATAX_JOB_CONTENT).size();

this.needChannelNumber = Math.min(this.needChannelNumber, taskNumber);
PerfTrace.getInstance().setChannelNumber(needChannelNumber);
```
从上面的代码看出，在不配置splitPk的情况下，单表etl不管配置channel值为大于一的任何值，最后的channel数都为1。
公平的分配 task 到对应的 taskGroup中，返回Configuration集合。将执行模式置为STANDALONE,交给AbstractScheduler，启动所有的任务线程startAllTaskGroup(configurations)。
```
@Override
public void startAllTaskGroup(List<Configuration> configurations) {
	this.taskGroupContainerExecutorService = Executors
		.newFixedThreadPool(configurations.size());
	for (Configuration taskGroupConfiguration : configurations) {
	    TaskGroupContainerRunner taskGroupContainerRunner = newTaskGroupContainerRunner(taskGroupConfiguration);
	    this.taskGroupContainerExecutorService.execute(taskGroupContainerRunner);
	}
	this.taskGroupContainerExecutorService.shutdown();
}
```
真正担任执行的是TaskGroupContainer.start()方法，该方法参与状态汇报和task启动，并实现自动容错机制。具体的sql执行由plugin对应数据库代码完成。
```
 while (true) {
    	//1.判断task状态
    	boolean failedOrKilled = false;
    	Map<Integer, Communication> communicationMap = containerCommunicator.getCommunicationMap();
    	for(Map.Entry<Integer, Communication> entry : communicationMap.entrySet()){
    		Integer taskId = entry.getKey();
    		Communication taskCommunication = entry.getValue();
           	.............
    	
        // 2.发现该taskGroup下taskExecutor的总状态失败则汇报错误
        if (failedOrKilled) {
            lastTaskGroupContainerCommunication = reportTaskGroupCommunication(
                    lastTaskGroupContainerCommunication, taskCountInThisTaskGroup);

            throw DataXException.asDataXException(
                    FrameworkErrorCode.PLUGIN_RUNTIME_ERROR, lastTaskGroupContainerCommunication.getThrowable());
        }
        //3.有任务未执行，且正在运行的任务数小于最大通道限制
        Iterator<Configuration> iterator = taskQueue.iterator();
        while(iterator.hasNext() && runTasks.size() < channelNumber){
            Configuration taskConfig = iterator.next();
            Integer taskId = taskConfig.getInt(CoreConstant.TASK_ID);
            int attemptCount = 1;
            TaskExecutor lastExecutor = taskFailedExecutorMap.get(taskId);
            if(lastExecutor!=null){
                attemptCount = lastExecutor.getAttemptCount() + 1;
                long now = System.currentTimeMillis();
                long failedTime = lastExecutor.getTimeStamp();
                if(now - failedTime < taskRetryIntervalInMsec){  //未到等待时间，继续留在队列
                    continue;
                }
		.............
        //4.任务列表为空，executor已结束, 搜集状态为success--->成功
        if (taskQueue.isEmpty() && isAllTaskDone(runTasks) && containerCommunicator.collectState() == State.SUCCEEDED) {
        	// 成功的情况下，也需要汇报一次。否则在任务结束非常快的情况下，采集的信息将会不准确
            lastTaskGroupContainerCommunication = reportTaskGroupCommunication(
                    lastTaskGroupContainerCommunication, taskCountInThisTaskGroup);
            LOG.info("taskGroup[{}] completed it's tasks.", this.taskGroupId);
            break;
        }
        // 5.如果当前时间已经超出汇报时间的interval，那么我们需要马上汇报
        long now = System.currentTimeMillis();
        if (now - lastReportTimeStamp > reportIntervalInMillSec) {
            lastTaskGroupContainerCommunication = reportTaskGroupCommunication(
                    lastTaskGroupContainerCommunication, taskCountInThisTaskGroup);
            lastReportTimeStamp = now;
           //taskMonitor对于正在运行的task，每reportIntervalInMillSec进行检查
            for(TaskExecutor taskExecutor:runTasks){
                taskMonitor.report(taskExecutor.getTaskId(),this.containerCommunicator.getCommunication(taskExecutor.getTaskId()));
            }
        }
        Thread.sleep(sleepIntervalInMillSec);
    }
```

不断循环communication传过来的消息进行收集处理。
```
	while (true) {
	/**
	 * step 1: collect job stat
	 * step 2: getReport info, then report it
	 * step 3: errorLimit do check
	 * step 4: dealSucceedStat();
	 * step 5: dealKillingStat();
	 * step 6: dealFailedStat();
	 * step 7: refresh last job stat, and then sleep for next while
	 *
	 * above steps, some ones should report info to DS
	 *
	 */
	Communication nowJobContainerCommunication = this.containerCommunicator.collect();
	nowJobContainerCommunication.setTimestamp(System.currentTimeMillis());
	LOG.debug(nowJobContainerCommunication.toString());
	//汇报周期
	long now = System.currentTimeMillis();
	if (now - lastReportTimeStamp > jobReportIntervalInMillSec) {
	    Communication reportCommunication = CommunicationTool
		    .getReportCommunication(nowJobContainerCommunication, lastJobContainerCommunication, totalTasks);
	    this.containerCommunicator.report(reportCommunication);
	    lastReportTimeStamp = now;
	    lastJobContainerCommunication = nowJobContainerCommunication;
	}
	errorLimit.checkRecordLimit(nowJobContainerCommunication);
	if (nowJobContainerCommunication.getState() == State.SUCCEEDED) {
	    LOG.info("Scheduler accomplished all tasks.");
	    break;
	}
	if (isJobKilling(this.getJobId())) {
	    dealKillingStat(this.containerCommunicator, totalTasks);
	} else if (nowJobContainerCommunication.getState() == State.FAILED) {
	    dealFailedStat(this.containerCommunicator, nowJobContainerCommunication.getThrowable());
	}
	Thread.sleep(jobSleepIntervalInMillSec);
	}
```
post方法对于reader啥也没干,对writer对处理数据后要做的事儿。
```
 if (null != renderedPostSqls && !renderedPostSqls.isEmpty()) {
    // 说明有 postSql 配置，则此处删除掉
    originalConfig.remove(Key.POST_SQL);

    Connection conn = DBUtil.getConnection(this.dataBaseType,
            jdbcUrl, username, password);

    LOG.info(
            "Begin to execute postSqls:[{}]. context info:{}.",
            StringUtils.join(renderedPostSqls, ";"), jdbcUrl);
    WriterUtil.executeSqls(conn, renderedPostSqls, jdbcUrl, dataBaseType);
    DBUtil.closeDBResources(null, null, conn);
}
```
好啦，大致重要的方法就这些
