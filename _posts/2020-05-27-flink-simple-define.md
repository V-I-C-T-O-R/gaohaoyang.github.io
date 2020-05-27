---
layout: post
title:  "Flink基础概念"
categories: Flink
tags: Flink 大数据
author: Victor
---

* content
{:toc}

Apache Flink是一个分布式大数据流处理引擎，可对有限数据流和无限数据流进行有状态或无状态的计算，能够对各种规模大小的数据进行快速计算。
#### Flink概念
* Streams，流，又分为有限数据流与无限数据流，二者的区别在于无限数据流的数据会随时间的推演而持续增加，计算持续进行且不存在结束的状态。而相对的有限数据流数据大小固定，计算最终会完成并处于结束的状态。
* State，状态，在容错恢复和 Checkpoint 中有重要的作用。
* Time，分为事件时间、摄入时间、处理时间。Flink 的时间是我们判断业务状态是否滞后，数据处理是否及时的重要依据。
* API，API 通常分为三层，由上而下可分为 SQL/Table API、DataStream API、ProcessFunction 三层，API 的表达能力及业务抽象能力都非常强大，但越接近 SQL 层，表达能力会逐步减弱，抽象能力会增强。
<!-- more -->

#### Flink优势  
* 状态容错
* 状态维护
* 多种Event-Time
* Watermarks即水印，Watermarks在Flink中属于特殊事件，当某个运算值收到带有时间戳"T"的水印时就意味着它不会接收到任何小于"T"时间戳的数据了。
* 状态保存与迁移，保存点（Savepoint），Savepoint跟Checkpoint 的差别在于检查点是Flink对于一个有状态的应用在运行中利用分布式快照持续周期性的产生Checkpoint，而Savepoint则是手动产生的 Checkpoint。

#### Flink DataStream API
Word Count 示例
```
//设置运行环境
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
//配置数据源读取数据
DataStream text = env.readTextFile ("input");
//进行转换
DataStream<Tuple2<String, Integer>> counts = text.flatMap(new Tokenizer()).keyBy(0).sum(1);
//配置写出数据位置
counts.writeAsText("output");
//提交执行(这里是真正开始执行，将DAG逻辑提交到集群)
env.execute("Streaming WordCount");
```
#### WindowAssigner,Evictor,Trigger
WindowAssigner负责将每条输入的数据分发到正确的window中(一条数据可能同时分发到多个 Window 中)。Flink 提供了几种通用的WindowAssigner：滚动窗口(窗口间的元素无重复)，滑动窗口(窗口间的元素可能重复)，会话窗口以及global window。如果需要自己定制数据分发策略，则可以实现一个类继承自 WindowAssigner。  
evictor() 主要用于做一些数据的自定义操作，可以在执行用户代码之前，也可以在执行用户代码之后。org.apache.flink.streaming.api.windowing.evictors.Evictor 的 evicBefore 和 evicAfter 两个方法。Flink 提供了如下三种通用的 evictor：
* CountEvictor 保留指定数量的元素
* DeltaEvictor 通过执行用户给定的 DeltaFunction 以及预设的threshold，判断是否删除一个元素。
* TimeEvictor 设定一个阈值 interval，删除所有不再max_ts – interval范围内的元素，其中 max_ts 是窗口内时间戳的最大值。  

trigger() 用来判断一个窗口是否需要被触发，每个 WindowAssigner 都自带一个默认的 trigger，如果默认的 trigger 不能满足你的需求，则可以自定义一个类，继承自 Trigger 即可，我们详细描述下 Trigger 的接口以及含义：
* onElement()：每次往 window 增加一个元素的时候都会触发
* onEventTime()：当 event-time timer 被触发的时候会调用
* onProcessingTime()：当 processing-time timer 被触发的时候会调用
* onMerge()：对两个 trigger 的 state 进行 merge 操作
* clear()：window销毁的时候被调用  
上面的接口中前三个会返回一个 TriggerResult，TriggerResult 有如下几种可能的选择：
* CONTINUE：不做任何事情
* FIRE：触发 window
* PURGE：清空整个 window 的元素并销毁窗口
* FIRE_AND_PURGE：触发窗口，然后销毁窗口

#### 时间
在 Flink中Time分为三种 Event-Time，Processing-Time以及Ingestion-Time：
* Event-Time：事件时间，表示事件发生的时间
* Processing-Time：处理时间，表示处理消息的时间
* Ingestion-Time：摄入时间，表示进入到系统的时间  

更多详细内容请关注Flink中文社区
