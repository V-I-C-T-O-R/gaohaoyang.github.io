import sys
import time

import pymysql.cursors
import requests

AZKABANURL = 'http://localhost:8443'
USERNAME = 'test'
PASSWORD = 'test'

mysql_host = '127.0.0.1'
mysql_port = 3306
mysql_user = 'test'
mysql_pass = 'test'
mysql_db = 'test'


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


# 判断任务是否在数据库中存在
def judge_online(project_name):
    sql = "select * from projects where name='{}'".format(project_name)
    excute_result = excute(sql)
    return excute_result


# 获取项目执行完毕的最新时间
def get_latest_record(sql):
    excute_result = excute(sql)
    return excute_result

def get_session_id():
    '''获取azkaban登录session_id'''
    try:
        params = {
            'action': 'login',
            'username': USERNAME,
            'password': PASSWORD
        }
        r = requests.post(AZKABANURL, data=params, headers={
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
            'X-Requested-With': 'XMLHttpRequest'
        })

        if r.status_code == 200 and 'session.id' in r.json():
            session_id = r.json()['session.id']
            print('[INFO] session_id:', session_id)
            return session_id
    except Exception as e:
        print('[FAIL] getsession_id: %s' % str(e))
        return None


def exec_flows(session_id, project_name, flow_name):
    '''执行flow'''
    try:
        params_list = {}
        params_list['session.id'] = session_id
        params_list['ajax'] = 'executeFlow'
        params_list['project'] = project_name
        params_list['flow'] = flow_name

        r = requests.post(AZKABANURL + "/executor", data=params_list)

        if r.status_code == 200:
            execid = r.json()['execid']
            print('%s项目%s流开始执行,execId:%s' % (project_name, flow_name, execid))
            return execid
    except Exception as e:
        print('Flow执行失败:%s' % str(e))
        return None


def get_exec_id(session_id, project, flow):
    '''获取azkaban任务的运行id'''
    try:
        r = requests.get('%s/manager?session.id=%s&ajax=fetchFlowExecutions&project=%s&flow=%s&start=0&length=3' % (
            AZKABANURL, session_id, project, flow), verify=False)

        if r.status_code == 200 and 'executions' in r.json():
            execIds = []
            for execution in r.json()['executions']:
                execIds.append(execution['execId'])
            print('[INFO] execIds:', execIds)
            return execIds
        else:
            raise Exception('[FAIL] getExecId: status_code(%d), %s' % (r.status_code, r.json()))
    except Exception as e:
        print('[FAIL] getExecId: %s' % str(e))
        sys.exit(-1)


def get_running_status(session_id, exec_id):
    '''获取azkaban任务的运行状态'''
    try:
        r = requests.post('%s/executor' % AZKABANURL, verify=False, data={'session.id': session_id,
                                                                          'ajax': 'fetchexecflow',
                                                                          'execid': exec_id})
        if r.status_code == 200 and 'nodes' in r.json():
            return r.json()
        else:
            raise Exception('[FAIL] getRunningStatus: status_code(%d), %s' % (r.status_code, r.json()))
    except Exception as e:
        print('[FAIL] getRunningStatus: %s' % str(e))
        sys.exit(-1)


def check_status(session_id, project, flow):
    '''检查azkaban project任务的所有运行状态'''
    exec_ids = get_exec_id(session_id, project, flow)

    for exec_id in exec_ids:
        runningStatus = get_running_status(project, exec_id)
        for rs in runningStatus:
            id, attempt, status = rs['id'], rs['attempt'], rs['status']
            print('execId: %s, id: %s, attempt: %d, status: %s' % (exec_id, id, attempt, status))


#执行依赖当天某个跨项目工作流
def exec_across_dependencies_task(session_id, depend_project, ready_project, ready_flow):
    online_result = judge_online(depend_project)
    if len(online_result) == 0:
        print("任务表{}还没有上线".format(depend_project))
        sys.exit(1)
    else:
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
                 LIMIT 1""".format(depend_project)
        while 1:

            exec_result = get_latest_record(sql)
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

#执行依赖当天某个跨项目工作流的单个job
def exec_across_dependencies_task(session_id, depend_project,depend_job_id, ready_project, ready_flow):
    online_result = judge_online(depend_project)
    if len(online_result) == 0:
        print("任务表{}还没有上线".format(depend_project))
        sys.exit(1)
    else:
        sql = """SELECT * FROM (
                    SELECT t2.name AS project_name, t1.*
                    FROM (
                        SELECT project_id, flow_id,exec_id, status, substr(FROM_UNIXTIME(end_time / 1000), 1, 19) AS end_time
                        FROM azkaban.execution_jobs
                        WHERE status = 50 AND substr(FROM_UNIXTIME(end_time/1000), 1, 19)>=DATE_FORMAT(CURDATE(),'%Y-%m-%d %H:%i:%s') and job_id = '{}'
                    ) t1
                        INNER JOIN (
                            SELECT id,name 
                            FROM projects
                            WHERE name = '{}'
                        ) t2
                        ON t1.project_id = t2.id
                    ORDER BY end_time DESC
                    ) t
                    LIMIT 1""".format(depend_job_id,depend_project)
        while 1:

            exec_result = get_latest_record(sql)
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

if __name__ == '__main__':
    session_id = get_session_id()
    if not session_id:
        print('获取session失败,异常退出')
    exec_across_dependencies_task(session_id, 'hive_test', 'hive_test', 'end')
