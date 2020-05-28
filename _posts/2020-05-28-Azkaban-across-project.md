---
layout: post
title:  "Azkaban跨项目依赖"
categories: Azkaban
tags: Azkaban
author: Victor
---

* content
{:toc}

Azkaban是由Linkedin开源的一个批量工作流任务调度器。用于在一个工作流内以一个特定的顺序运行一组工作和流程。Azkaban定义了一种KV文件格式来建立任务之间的依赖关系，并提供一个易于使用的web用户界面维护和跟踪你的工作流。在数据领域，Azkaban非常流行，但是原生的Azkaban也存在不少缺陷。比如：跨项目依赖、自带用户管理功能弱、中文支持乱码等等。
<!-- more -->
最近项目规划需要，又拾起了Azkaban调度器，首先遇到的便是跨项目调度问题。在官方的源代码中，是不支持跨项目调度依赖的。从代码工作量上来评估，短时间内个人完成源代码的二次开发有点困难。故而求其次，开始从数据库元数据开始入手，幸而Azkaban本身也有Restful接口可以直接躁动起来吧！

整块跨项目调度依赖分为三个部分：Mysql状态查询、轮询依赖的项目状态、轮询执行的当前项目状态。  
#### Mysql状态查询
    Mysql状态查询部分比较好理解，从相关数据表中获取当前指定项目流的执行情况，从而可以将依赖项目的完成情况查询出来。实现示例如下:  
    ```
    def excute(sql):
    # azkaban关于任务依赖所在的mysql
    config = {'host': mysql_host, 'port': mysql_port, 'user': mysql_user, 'password': mysql_pass, 'db': mysql_db,
              'charset': 'utf8mb4', 'cursorclass': pymysql.cursors.DictCursor, }
    connection = pymysql.connect(**config)
    with connection.cursor() as cursor1:
        cursor1.execute(sql)
        result = cursor1.fetchall()
        connection.commit()
    cursor1.close()
    connection.close()
    return result

    ```
#### 轮询依赖的项目状态
    这里依靠Mysql状态查询模块对依赖项目的状态进行判断，是否可以执行当前项目工作流。示例代码：  
    ```
    # 判断任务是否在数据库中存在
	def judge_online(project_name):
	    sql = "select * from projects where name='{}'".format(project_name)
	    excute_result = excute(sql)
	    return excute_result


	# 获取项目执行完毕的最新时间
	def get_latest_record(project_name):
	    sql = """SELECT *
	             FROM (
	                SELECT t2.name AS project_name, t1.*
	                FROM (
	                    SELECT project_id, flow_id, status
	                        , substr(FROM_UNIXTIME(start_time / 1000), 1, 19) AS start_time
	                        , substr(FROM_UNIXTIME(end_time / 1000), 1, 19) AS end_time
	                        , enc_type
	                    FROM azkaban.execution_flows
	                    WHERE status = 50 AND substr(FROM_UNIXTIME(end_time/1000), 1, 19)>=DATE_FORMAT(CURDATE(),'%Y-%m-%d %H:%i:%s')
	                ) t1
	                    INNER JOIN (
	                        SELECT *
	                        FROM projects
	                        WHERE name = '{}'
	                    ) t2
	                    ON t1.project_id = t2.id
	                ORDER BY end_time DESC
	             ) t
	             LIMIT 1""".format(project_name)
	    excute_result = excute(sql)
	    return excute_result
    ```
#### 轮询执行的当前项目状态
    当得到依赖项目执行完成切成功的信息后，开始通过API调用执行当前指定的工作流，并持续监听执行状态，直到执行完成。示例代码为：  
    ```
    def exec_across_dependencies_task(session_id, depend_project, ready_project, ready_flow):
    online_result = judge_online(depend_project)
    if len(online_result) == 0:
        print("任务表{}还没有上线".format(depend_project))
        sys.exit(1)
    else:
        while 1:

            exec_result = get_latest_record(depend_project)
            if len(exec_result) != 0:
                print("{}同步任务执行成功！开始执行{}".format(depend_project, ready_project))
                exec_id = exec_flows(session_id, ready_project, ready_flow)
                if not exec_id:
                    print('%s项目执行失败' % ready_project)
                    return
                print('%s项目%s流执行开始' % (ready_project, ready_flow))
                while 1:
                    running_status = get_running_status(session_id, exec_id)['status']
                    if running_status == 'SUCCEEDED':
                        print("{}项目{}流完成".format(depend_project, ready_project))
                        break
                    print("{}项目{}流正在执行...".format(depend_project, ready_project))
                    time.sleep(3)

                break
            print("%s项目还没有执行，请等待..." % depend_project)
            time.sleep(5)
    ```
至此，跨项目依赖的问题有了一个较快可解决的落地方案。具体源码可点击[跨任务依赖](https://V-I-C-T-O-R.github.io/code/azkaban-across-project.py)查看