---
layout: post
title:  "RDBMS准实时导入数据到Hbase"
categories: ETL
tags: ETL 实时 Hbase
author: Victor
---

* content
{:toc}

<p>
新的业务场景往往会触发出新的技术延伸。在数据处理的领域，不规范操作而没有及时更新关系数据库行的更新时间列往往导致常规的增量统计手段束手无策。最近的技术挑战便是这样，在Sqlserver和Mysql的数据库中由于不规范化操作，无法通过时间戳来做到早期的增量数据更新，这也就有了实时捕获更新的需求。对于这块我也算是比较新，之前都是写代码，做开发上功能，架构和技术选型之类的一个人抗不多。
</p>
<!-- more -->
#### 技术选型

##### 关于Mysql实时数据捕获
Mysql是非常流行的关系型数据库，对于它的数据变更捕获之前就有比较多的方案，比如阿里巴巴的canal,在canal上更自动化的Otter。根据整体规划，选择了自建canal来作为数据源抽取工具
##### 关于Sql Server实时数据捕获
Sql Server的实时捕获方案在实现上可以借鉴的并不多，还是国外Confluent公司根据kafka做了相关实现，依靠Sql Server数据库的CDC和Data Tracking机制来进行数据捕获

#### 技术挑战
* 分表分库的四万多张表
* 关系型数据库数据保证不丢失
* 实时捕获和全量数据对接协调
* 数据完整性效验

#### 技术实施
1. 设计Hbase表结构，根据分表分库原则设计rowkey,CF,数据生效时间，是否已经删除
2. 全量脚本开发
根据流程需要首先在Hbase上面建立对应的命名空间，表，列簇，与Hive相互映射的建表语句
3. 生成Datax做全量任务导出到对应的Hbase表中的json
4. 分模块开发，对canal,kafka,hbase部分进行对接
5. Canal分布式部署，Confluent平台部署
6. 数据对接与log审查对数
7. 测试与数据效验
8. 后续观察

#### 技术总结
* Canal分布式部署后，手动捕获任何处理解析数据的异常防止数据丢失
* Hbase插入数据过程中需要指定好数据类型，防止与全量数据类型不一致造成hive映射表乱码
* Kafka集群min isr设置，ack='all'，retry次数，重试间隔时间，最大拉取字节数，topic分区数，分区备份数，auto.offset.reset，enable.auto.commit等配置保证消息可靠性
* 由于每次测试周期较长，patient
* 坑多请坚持

#### Kafka吞吐量与数据可靠性的取舍
三个broker,8核,8G资源分配，isr为2的情况下，吞吐量最大值为400/s左右

* kafka ack=all,保证所有副本都返回后才确认
* kafka retrys=30,失败之后默认重试30次
* kafka 消息大小最大2k字节,最小一百字节。消息大小对吞吐量影响很大
* produver 选择同步get发送，保证收到响应之后再返回，用以判定是否确认offset或回滚
