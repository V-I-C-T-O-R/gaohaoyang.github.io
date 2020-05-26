---
layout: post
title:  "Flume增量采集DB数据"
categories: FLume
tags: FLume 增量
author: Victor
---

* content
{:toc}


<p>
2019年过去大半，心境不悲不喜，机遇不痛不痒，心忧所惑。
</p>

业务场景比较杂，美其名曰是自动化运维，奈何数据不规范，跨部门太复杂，不得不采用二梯度的法子。说起关系数据库的数据采集，一般是Mysql的binlog,Sqlserver的CDC,Oracle的ogg等。
由于实时采集方案不满足现有业务的监控需要，退而求其次进行增量数据的抽取。面对多种数据源的增量抽取，同时时间戳规范不一致(时间戳,DateTime格式都有)，通用的方案有kafka connector,Logstash自定义，Flume自定义等。鉴于数据技术栈现有体系包含Flume的情况下，采用Flume增量抽取的方案。  
Flume-ng本身对于增量抽取是没有适配，尤其是包含多种数据源的时间格式不规范的情况，针对[flume-ng-sql-source](https://github.com/keedio/flume-ng-sql-source)的开源项目进行修改,修改部分:  
- 更改输出格式为json
- 根据增量时间字段来进行增量查询数据,支持int型时间戳和1970-01-01 00:00:00字符串类型时间
- 增加全量和增量属性  
<!-- more -->
配置示例如下:

```properties
# For each one of the sources, the type is defined
agent.channels = memoryChannel
agent.sources = sqlSource
agent.sinks = kafkaSink


# For each one of the sources, the type is defined
agent.sources.sqlSource.type = org.keedio.flume.source.SQLSource

agent.sources.sqlSource.hibernate.connection.url = jdbc:mysql://127.0.0.1:3306/test?autoReconnect=true

# Hibernate Database connection properties
agent.sources.sqlSource.hibernate.connection.user = test
agent.sources.sqlSource.hibernate.connection.password = test
agent.sources.sqlSource.hibernate.connection.autocommit = true
agent.sources.sqlSource.hibernate.dialect = org.hibernate.dialect.MySQL5Dialect
agent.sources.sqlSource.hibernate.connection.driver_class = com.mysql.jdbc.Driver
agent.sources.sqlSource.hibernate.temp.use_jdbc_metadata_defaults=false

agent.sources.sqlSource.table = test
# Columns to import to kafka (default * import entire row)
agent.sources.sqlSource.columns.to.select = *
# Query delay, each configured milisecond the query will be sent
agent.sources.sqlSource.run.query.delay=60000
# Status file is used to save last readed row
agent.sources.sqlSource.status.file.path = /data/flume_status
agent.sources.sqlSource.status.file.name = test

# Custom query
agent.sources.sqlSource.start.from = 2019-07-03 14:52:00
agent.sources.sqlSource.time.column = updateTime
agent.sources.sqlSource.time.column.type = string
agent.sources.sqlSource.source.transfer.method = incrementing

agent.sources.sqlSource.batch.size = 2000
agent.sources.sqlSource.max.rows = 3000

agent.sources.sqlSource.hibernate.connection.provider_class = org.hibernate.connection.C3P0ConnectionProvider
agent.sources.sqlSource.hibernate.c3p0.min_size=1
agent.sources.sqlSource.hibernate.c3p0.max_size=3


agent.channels.memoryChannel.type = memory
agent.channels.memoryChannel.capacity = 4000
agent.channels.memoryChannel.transactionCapacity = 2000
agent.channels.memoryChannel.byteCapacityBufferPercentage = 20

agent.channels.memoryChannel.keep-alive = 60
agent.channels.memoryChannel.capacity = 1000000
agent.sources.sqlSource.channels = memoryChannel
agent.sinks.kafkaSink.channel = memoryChannel

######配置kafka sink ##############################
agent.sinks.kafkaSink.type = org.apache.flume.sink.kafka.KafkaSink
#kafka话题名称
agent.sinks.kafkaSink.kafka.topic = test
#kafka的地址配置
agent.sinks.kafkaSink.kafka.bootstrap.servers = 127.0.0.1:9092
#设置序列化方式
agent.sinks.kafkaSink.serializer.class=kafka.serializer.StringEncoder
agent.sinks.kafkaSink.kafka.producer.acks = 1
agent.sinks.kafkaSink.flumeBatchSize = 100
```


###### 
这是个不平凡的时代，这也是个寂寞急躁的时代，站住脚，迈开腿，绷紧肌肉，咬紧牙关，挺过去，或许，诗才在远方！共勉之，同行之
事实上，属于我们的时代刚刚开始，还等什么呢？  

项目源码详情请看[flume-ng-sql-source](https://github.com/V-I-C-T-O-R/flume-ng-sql-source)  
