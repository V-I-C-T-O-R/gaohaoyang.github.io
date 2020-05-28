---
layout: post
title:  "Flink水印理解"
categories: Flink
tags: Flink 大数据
author: Victor
---

* content
{:toc}

水印，用于告诉系统事件时间中的执行进度，时间戳的分配随着水印的生成。水印的依赖条件是窗口，水印只是决定了窗口的触发时间，watermark是用于处理乱序事件的。
有两种方式可以分配时间戳和生成水印：
* 直接在数据流源中进行
* 通过timestamp assigner和watermark generator生成
> 注意：如果指定多次watermark，后面指定的会覆盖前面的值；多并行度的情况下，watermark对齐会取所有channel最小的watermark；