---
layout: post
title:  "Datax源码分析一"
categories: Datax
tags: datax 源代码
author: Victor
---

* content
{:toc}

#### 前传
  初始认识Datax是刚进入公司的第二个月，当时数据中心架构表现极其不稳定，原本从线上数据库定时同步数据到Hdfs做中转清洗，最后再插入到部门mysql，但是由于服务器资源占用和程式本身的不稳定性，凌晨执行的任务失败后得早上上班才能执行，并且执行过程超过四个小时，严重阻碍了正常工作。鉴于此，经过调研和对整套体系的熟悉，发现使用Datax直接可以用来替代现有的中转流程，并且实践证明比原来的效率提高了50%，整个ETL流程只需要一个多小时。现在整套服务基本稳定运行，本着更加懂它用它的原则，开始看Datax的源代码。

#### 开始(以mysql为例)
从[www.github:https://github.com/alibaba/DataX](github:https://github.com/alibaba/DataX/)下载源码，通过idea阅读。Datx根目录下core包包含了整个执行框架，其中com.alibaba.datax.core.Engine是整个Java任务的入口，core/src/main/bin/datax.py是服务端打包后执行的入口。

***datax.py片段***
```
ENGINE_COMMAND = "java -server ${jvm} %s -classpath %s  ${params} com.alibaba.datax.core.Engine -mode ${mode} -jobid ${jobid} -job ${job}" % (DEFAULT_PROPERTY_CONF, CLASS_PATH)
```
Engine接收三个主要参数:job,jobid,mode，其中job代表任务配置json的位置，jobid表示此次任务的id，默认为-1，mode表示执行的模式。将job路径的文件内容转换成Configuration,将项目本身存在在${datax.home}/conf/core.json中的文件与自定义的配置文件合并，更新core.json有而自定义job中没有的配置。
```
public Configuration merge(final Configuration another,
		boolean updateWhenConflict) {
	Set<String> keys = another.getKeys();

	for (final String key : keys) {
		// 如果使用更新策略，凡是another存在的key，均需要更新
		if (updateWhenConflict) {
			this.set(key, another.get(key));
			continue;
		}

		// 使用忽略策略，只有another Configuration存在但是当前Configuration不存在的key，才需要更新
		boolean isCurrentExists = this.get(key) != null;
		if (isCurrentExists) {
			continue;
		}

		this.set(key, another.get(key));
	}
	return this;
}
```
初始化plugin中的配置，配置string,btye,date类型的格式。
```
public static void bind(final Configuration configuration) {
		StringCast.init(configuration);
		DateCast.init(configuration);
		BytesCast.init(configuration);
}
```
根据core.container.model变量来判断是任务组还是一个任务，实例化对应的JobContainer或TaskGroupContainer,启动对应的start方法。

#### 重点
根据isDry属性判断是不是任务预检查，如果isDry为true,则只执行preCheck方法。该方法设置基本的jobPlugin,communicator，检查读写plugin是否有每个表的读写权限，以及querySql,splikPK是否正确。
```
 /*verify query*/
                ResultSet rs = null;
                try {
                    DBUtil.sqlValid(querySql,dataBaseType);
                    if(i == 0) {
                        rs = DBUtil.query(conn, querySql, fetchSize);
                    }
                } catch (ParserException e) {
                    throw RdbmsException.asSqlParserException(this.dataBaseType, e, querySql);
                } catch (Exception e) {
                    throw RdbmsException.asQueryException(this.dataBaseType, e, querySql, table, userName);
                } finally {
                    DBUtil.closeDBResources(rs, null, null);
                }
            /*verify splitPK*/
                try{
                    if (splitPkSqls != null && !splitPkSqls.isEmpty()) {
                        splitPkSql = splitPkSqls.get(i).toString();
                        DBUtil.sqlValid(splitPkSql,dataBaseType);
                        if(i == 0) {
                            SingleTableSplitUtil.precheckSplitPk(conn, splitPkSql, fetchSize, table, userName);
                        }
                    }
                } catch (ParserException e) {
                    throw RdbmsException.asSqlParserException(this.dataBaseType, e, splitPkSql);
                } catch (DataXException e) {
                    throw e;
                } catch (Exception e) {
                    throw RdbmsException.asSplitPKException(this.dataBaseType, e, splitPkSql,this.splitPkId.trim());
                }

```
如果isDry为false,则依次执行七个步骤：preHandle，init，split，schedule，post，postHandle，invokeHooks。
preHandle方法：配置对应plugin的handler
init方法：预处理jobId,初始化reader,writer对应的plugin
split方法(核心)：
首先Reader根据json配置中的channel参数指定建议的切分个数，然后按照isTableMode参数来判断是指定Table方式还是querySql方式。isTableMode为True,计算eachTableShouldSplittedNumber的数值，即eachTableShouldSplittedNumber是单表应该切分的份数。如果splitPK有值且eachTableShouldSplittedNumber>1且是单表，则eachTableShouldSplittedNumber = eachTableShouldSplittedNumber * 5;尝试对每个表，切分为eachTableShouldSplittedNumber 份
```
 for (String table : tables) {
                        tempSlice = sliceConfig.clone();
                        tempSlice.set(Key.TABLE, table);

                        List<Configuration> splittedSlices = SingleTableSplitUtil
                                .splitSingleTable(tempSlice, eachTableShouldSplittedNumber);

                        splittedConfigs.addAll(splittedSlices);
}
```
其中，SingleTableSplitUtil.splitSingleTable有如下作用:
1.用于查询出对应的表按splitPk切分对应的对大值和最小值。
```
 public static String genPKSql(String splitPK, String table, String where){
        String minMaxTemplate = "SELECT MIN(%s),MAX(%s) FROM %s";
        String pkRangeSQL = String.format(minMaxTemplate, splitPK, splitPK,
                table);
        if (StringUtils.isNotBlank(where)) {
            pkRangeSQL = String.format("%s WHERE (%s AND %s IS NOT NULL)",
                    pkRangeSQL, where, splitPK);
        }
        return pkRangeSQL;
}
```
2.对splitPk的跨度做eachTableShouldSplittedNumber粒度的区分，将column,table,where和上一步的splitPk做拼接。
```
for (String range : rangeList) {
                Configuration tempConfig = configuration.clone();

                tempQuerySql = buildQuerySql(column, table, where)
                        + (hasWhere ? " and " : " where ") + range;

                allQuerySql.add(tempQuerySql);
                tempConfig.set(Key.QUERY_SQL, tempQuerySql);
                pluginParams.add(tempConfig);
}
```
isTableMode为False,表示是querySql模式，不拼接，直接返回list。
然后，依据Reader的任务数，Writer做对应的切分。分为单表和多表，单表即：
```
//处理单表的情况
if (tableNumber == 1) {
    //由于在之前的  master prepare 中已经把 table,jdbcUrl 提取出来，所以这里处理十分简单
    for (int j = 0; j < adviceNumber; j++) {
        splitResultConfigs.add(simplifiedConf.clone());
    }

    return splitResultConfigs;
}
```
其中，adviceNumber是Reader切分的数量。
多表则得判断配置的表的个数是否与adviceNumber一样，否则跑出异常。一样则分别为每个表添加一份sql。
```
for (String table : tables) {
        Configuration tempSlice = sliceConfig.clone();
        tempSlice.set(Key.TABLE, table);
        tempSlice.set(Key.PRE_SQL, renderPreOrPostSqls(preSqls, table));
        tempSlice.set(Key.POST_SQL, renderPreOrPostSqls(postSqls, table));
        splitResultConfigs.add(tempSlice);
    }
```
接着整合上几步的Reader配置和Writer配置，一一对应
```
for (int i = 0; i < readerTasksConfigs.size(); i++) {
    Configuration taskConfig = Configuration.newDefault();
    taskConfig.set(CoreConstant.JOB_READER_NAME,
            this.readerPluginName);
    taskConfig.set(CoreConstant.JOB_READER_PARAMETER,
            readerTasksConfigs.get(i));
    taskConfig.set(CoreConstant.JOB_WRITER_NAME,
            this.writerPluginName);
    taskConfig.set(CoreConstant.JOB_WRITER_PARAMETER,
            writerTasksConfigs.get(i));

    if(transformerConfigs!=null && transformerConfigs.size()>0){
        taskConfig.set(CoreConstant.JOB_TRANSFORMER, transformerConfigs);
    }

    taskConfig.set(CoreConstant.TASK_ID, i);
    contentConfigs.add(taskConfig);
}
```
这里的taskConfig就是整合后的reader和wirter一一对应的配置。
schedule方法：未完待续.......