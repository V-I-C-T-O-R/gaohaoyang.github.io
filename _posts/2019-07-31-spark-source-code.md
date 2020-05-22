---
layout: post
title:  "Spark源码分析之初"
categories: Spark
tags: Spark 源代码
author: Victor
---

* content
{:toc}

彷徨过一段时间，可能是每个人工作一段时间之后都会产生一个瓶颈期，浑浑噩噩，感觉干不起什么大事儿，掀不出风浪来。打游戏，逛新闻，刷视频，一天转眼就过去了，实属惊心。渐渐的内心有个声音也提醒自己不能如此以往，想要提升影响力，没机遇的情况下只能提高实力。又突然受到友人打鸡血的激励，特有感恐须阅读优秀的源码来学习深层次的架构之美，故有此文章。

当然，故事的开头都是很凄凉的。阅读源代码，必须先download下来代码本身，鉴于很久之前在github上最新的master代码尝试过一次之后木然放弃，转而尝试apache官网的spark稳定版源码——2.4.3。下载下来之后根据本地自身的环境更改根pom文件中的scala版本、hadoop版本、java版本、maven版本再导入依赖，个人笔记本上的maven编译速度实在是不敢恭维，不得不在maven参数上做文章，Idea intellij setting maven的Thread中填入2C(表示每个核心用两个线程来执行)，runner的JVM Options中填入-XX:+TieredCompilation -XX:TieredStopAtLevel=1 -Dmaven.test.skip跳过不必要的测试。接下来在根目录下terminal执行mvn clean package进
行项目的编译，编译时间有点久，耐心等待。完成之后跑个examples中的例子，比如JavaLogQuery示例，在Configuration的VM options中填入-Dspark.master=local模拟本地运行即可(如果出现NoClassDefFoundError
错误，将pom文件中对应的依赖scope改为compile，就是有点多-_-)。

接下来详情请关注[spark-source-code](https://github.com/V-I-C-T-O-R/spark-source-code)

###### 如果需要交流，请联系我(ps:github有常用邮箱)