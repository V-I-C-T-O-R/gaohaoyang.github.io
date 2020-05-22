---
layout: post
title:  "基于Reis的第三方缓存设计"
categories: Redis
tags: redis 缓存 
author: Victor
---

* content
{:toc}

一般意义上的SSM项目中，Mybatis提供两级缓存机制，一级缓存是session级别，每一个会话一个缓存，二级缓存是namespace级别，针对每一个特定的namespace做全局缓存。但是，Mybatis自带的缓存仅仅也适用于Mapper中只有单表操作，而且二次开发并不是很方便。从自身项目出发，结合当前业务和服务特点，选择服务自身存在的redis作为缓存中间件，通过Spring的AOP拦截机制去对每一个Mybatis的namespace接口做监测，从而达到缓存提高查询效率的目的。
   
* 在具体的实施过程中，有几个关键点:
1 监测的接口方法传入的参数类型问题 
2 拦截器内部方法调用无法拦截 
3 同时有相同参数相同方法的请求进来时排队问题

**针对这三个问题，展开了技术开发。首选，参数类型除了基本类型，还有可能是Map,List,Set等常用集合，也会有自定义类实例，也就是说，当传参是自定义类实例时，必须按照顺序获取实例内部所有的属性值，以保证传入参数的唯一性。其次，内部方法在调用需要拦截的方法时，需要手动去实现实例注入进行调用，从而保证该行为能够被拦截。最后，需要对所有的请求方法做一个全局的线程安全集合，当多个相同请求在一段时间内到达时，只有一个请求在访问数据库，降低数据库负载。**

**`参数类型唯一`**
通过对拦截器拦截的方法类，方法，方法参数进行唯一值计算，进而得到对应的唯一缓存。
``` java
private String getCacheKey(String targetName, String methodName,
                               Object[] arguments) {
        StringBuffer result = new StringBuffer();
        result.append(targetName).append("_").append(methodName);
        if ((arguments != null) && (arguments.length != 0)) {
            for (int i = 0; i < arguments.length; i++) {
                if (arguments[i] == null) {
                    result.append("null");
                } else if (DataUtil.getType(arguments[i])) {
                    result.append(arguments[i]);
                } else if (arguments[i] instanceof Map) {
                    Map<String, Object> map = (Map<String, Object>) arguments[i];
                    Map<String, Object> treeMap = DataUtil.sortMapByKey(map);
                    DataUtil.getMapType(treeMap, result);
                } else if (arguments[i] instanceof List) {
                    List<Object> content = (List<Object>) arguments[i];
                    DataUtil.getListType(content, result);
                } else if (arguments[i] instanceof Set) {
                    Set<Object> subSet = (LinkedHashSet<Object>) arguments[i];
                    DataUtil.getSetType(subSet, result);
                } else {
                    DataUtil.dispose(arguments[i], result);
                }
            }
        }
        return cachePrefix + targetName + DataUtil.hashKeyForDisk(result.toString());
    }
```
即获取类名+方法名+参数字符串的md5值作为键,保证缓存唯一

**`内部方法调用无法拦截`**
Spring AOP拦截器无法拦截方法内部调用的方法，需要自定义调用类来获取对应的类来显示调用。
```java
<bean id="springContextUtil" class="com.laimi.data.util.SpringContextUtil" />
```
获取Spring容器上下文副本
```java
SpringContextUtil.getApplicationContext().getBean(Service.class).dataQuery(params)
```
调用上下文bean显示调用对应的类实例，进而调用对应的拦截器方法，拦截器可进行预处理。

**`排队问题`**
高并发时，同一个方法很可能有多个客户端在同时或者一段时间内都请求，如果仅仅是键唯一，并不能保证有效的降低数据库负载，所以必须保证相同请求，在上一个请求没有完成之前只能有一个能访问数据库。一般采用线程安全队列来解决消息发送问题，但是队列数据结构无法良好的保证随意随意存储和删除，所以，选择了线程安全的CopyOnWriteArrayList来实施。
```java
public class SafeList {
    private static volatile CopyOnWriteArrayList<String> safeList = null;
    private SafeList(){}
    public static CopyOnWriteArrayList getSafeList(){
        if(safeList==null){
            synchronized (SafeList.class){
                if(safeList==null){
                    safeList = new CopyOnWriteArrayList<String>();
                }
            }
        }
        return safeList;
    }
}
```
创建单例容器类
```java
  try {
                if (!collect.contains(key)) {
                    collect.add(key);
                    value = invocation.proceed();
                    if (value == null) {
                        collect.remove(key);
                        return value;
                    }
                    addToRedis(key, value);
                    collect.remove(key);
                } else {
                    if (!checkQueueKey(key, collect))
                        return null;
                    if (redisUtil.exists(key)) {
                        logger.info("查询缓存获取数据");
                        return redisUtil.get(key);
                    }
                }
```
条件判断key是否存在，从Redis获取缓存

自定义redis缓存方案能较好的解决当前访问量较高的情况，也是一次技术上的尝试，进步学习中......