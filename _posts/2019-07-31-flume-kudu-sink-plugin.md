---
layout: post
title:  "Flume数据插入Kudu"
categories: FLume
tags: FLume Kudu
author: Victor
---

* content
{:toc}


<p>
2019年过去大半，心境不悲不喜，机遇不痛不痒，心忧所惑。
</p>

接着上篇，数据的落地需要Kudu，继而做多数据源查询分析。之前的架构是从多数据源经过kafka,再spark streaming做处理，奈何此数据内容是运维场景，日志记录几十M都有可能存在。而通过spark
同时处理几十个Topic的上百个分区出现了数据不定时延期、数据倾斜等异常现象，不满足业务监控的时间差。从而从之前的状态中采取第二种可控的方案——重写flume sink直接插入Kudu(控制频次)。  
<!-- more -->
通过修改sink源码，重写了写入部分：
* 衔接json字符串转换source
* 根据传输的Json字段自动创建表

#### 用法示例  
```
agent.channels = fileChannel
agent.sources = sqlSource
agent.sinks = kuduSink

agent.sources.sqlSource.type = org.keedio.flume.source.SQLSource

agent.sources.sqlSource.hibernate.connection.url = jdbc:mysql://127.0.0.1:3306/test?autoReconnect=true

agent.sources.sqlSource.hibernate.connection.user = test 
agent.sources.sqlSource.hibernate.connection.password = test
agent.sources.sqlSource.hibernate.connection.autocommit = true
agent.sources.sqlSource.hibernate.dialect = org.hibernate.dialect.MySQL5Dialect
agent.sources.sqlSource.hibernate.connection.driver_class = com.mysql.jdbc.Driver
agent.sources.sqlSource.hibernate.temp.use_jdbc_metadata_defaults=false

agent.sources.sqlSource.table = items
# Columns to import to kafka (default * import entire row)
agent.sources.sqlSource.columns.to.select = *
# Query delay, each configured milisecond the query will be sent
agent.sources.sqlSource.run.query.delay= 300000
# Status file is used to save last readed row
agent.sources.sqlSource.status.file.path = /data/flume_status
agent.sources.sqlSource.status.file.name = items

# Custom query
agent.sources.sqlSource.start.from = 0 
agent.sources.sqlSource.source.transfer.method = bulk

agent.sources.sqlSource.batch.size = 3000
agent.sources.sqlSource.max.rows = 10000

agent.sources.sqlSource.hibernate.connection.provider_class = org.hibernate.connection.C3P0ConnectionProvider
agent.sources.sqlSource.hibernate.c3p0.min_size=1
agent.sources.sqlSource.hibernate.c3p0.max_size=3

# The channel can be defined as follows.
agent.channels.fileChannel.type = file
agent.channels.fileChannel.checkpointDir = /data/flume_checkpont/items
agent.channels.fileChannel.dataDirs = /data/flume_datadirs/items
agent.channels.fileChannel.capacity = 200000000
agent.channels.fileChannel.keep-alive = 180
agent.channels.fileChannel.write-timeout = 180
agent.channels.fileChannel.checkpoint-timeout = 300
agent.channels.fileChannel.transactionCapacity = 1000000

agent.sources.sqlSource.channels = fileChannel
agent.sinks.kuduSink.channel = fileChannel

######配置kudu sink ##############################
agent.sinks.kuduSink.type = com.flume.sink.kudu.KuduSink
agent.sinks.kuduSink.masterAddresses = 127.0.0.1:7051,127.0.0.2:7051,127.0.0.3:7051
agent.sinks.kuduSink.customKey = itemid
agent.sinks.kuduSink.tableName = items
agent.sinks.kuduSink.batchSize = 100
agent.sinks.kuduSink.namespace = test
agent.sinks.kuduSink.producer.operation = upsert
agent.sinks.kuduSink.producer = com.flume.sink.kudu.JsonKuduOperationProducer

```


###### 
这是个不平凡的时代，这也是个寂寞急躁的时代，站住脚，迈开腿，绷紧肌肉，咬紧牙关，挺过去，或许，诗才在远方！共勉之，同行之
事实上，属于我们的时代刚刚开始，还等什么呢？  

项目源码详情请看[flume-kudu-sink](https://github.com/V-I-C-T-O-R/flume-kudu-sink)  
