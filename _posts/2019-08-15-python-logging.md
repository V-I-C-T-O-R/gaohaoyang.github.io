---
layout: post
title:  "python logging日志正确的配置"
categories: Python
tags: Python 日志 配置
author: Victor
---

* content
{:toc}

之前用Flask写过python项目，关于日志部分使用了比较通用的配置方式——按天生成，大致观察它按天生成日志文件，有输出就没怎么在意。然而突然的有一天，发现貌似日志级别在记录上是不正确的，起初以为是我的打开方式不对，google了多方优秀人士的配置方式，具体配置大致长这样：  
```
import logging
import time,sys
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger('yyx')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

log_file_handler = TimedRotatingFileHandler(filename="log", when="S", interval=2)
log_file_handler.setFormatter(formatter)
log_file_handler.setLevel(logging.DEBUG)
logger.addHandler(log_file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
```
然而，这种配置文件并不能有效的生成定义级别的日志文件。在苦恼之余不得不得一步步的调试到第三方库logging中，不久之后，通用的python项目我修改出了大致如下配置(具体config.LOGGER_LEVEL配置按需更改)：  
```
logger = logging.getLogger()
logger.handlers.clear()#确保handlers为空

formatter = logging.Formatter(config.LOGGER_FORMAT)
fileHandler = TimedRotatingFileHandler(filename=config.LOGGER_FILE + 'info.log', when="D", interval=1,
                                   backupCount=7,
                                   encoding=config.LOGGER_CHARSET)
fileHandler.setFormatter(formatter)
fileHandler.setLevel(config.LOGGER_LEVEL)

console = logging.StreamHandler()
console.setFormatter(formatter)
console.setLevel(config.LOGGER_LEVEL)

logging.basicConfig(handlers=[console,fileHandler],level=logging.DEBUG, format=config.LOGGER_FORMAT, datefmt=config.LOGGER_DATE_FORMAT)

```
究其原因，与获取了不同的handlers有直接关系，此外就是basicConfig的传参。
此外就是basicConfig的传参里面叙述的很清楚，root.handlers为空的话就默认按文件名生成handler，且这个level直接作用在root上。
```
def basicConfig(**kwargs):
    _acquireLock()
    try:
        if len(root.handlers) == 0:
            handlers = kwargs.pop("handlers", None)
            if handlers is None:
                if "stream" in kwargs and "filename" in kwargs:
                    raise ValueError("'stream' and 'filename' should not be "
                                     "specified together")
            else:
                if "stream" in kwargs or "filename" in kwargs:
                    raise ValueError("'stream' or 'filename' should not be "
                                     "specified together with 'handlers'")
            if handlers is None:
                filename = kwargs.pop("filename", None)
                mode = kwargs.pop("filemode", 'a')
                if filename:
                    h = FileHandler(filename, mode)
                else:
                    stream = kwargs.pop("stream", None)
                    h = StreamHandler(stream)
                handlers = [h]
            dfs = kwargs.pop("datefmt", None)
            style = kwargs.pop("style", '%')
            if style not in _STYLES:
                raise ValueError('Style must be one of: %s' % ','.join(
                                 _STYLES.keys()))
            fs = kwargs.pop("format", _STYLES[style][1])
            fmt = Formatter(fs, dfs, style)
            for h in handlers:
                if h.formatter is None:
                    h.setFormatter(fmt)
                root.addHandler(h)
            level = kwargs.pop("level", None)
            if level is not None:
                root.setLevel(level)
            if kwargs:
                keys = ', '.join(kwargs.keys())
                raise ValueError('Unrecognised argument(s): %s' % keys)
    finally:
        _releaseLock()
```
此外需要注意的是就是不能重复添加handlers，例如这样：
```
logger.addHandler(console)
logger.addHandler(fileHandler)
logging.basicConfig(handlers=[console,fileHandler],level=logging.DEBUG, format=config.LOGGER_FORMAT, datefmt=config.LOGGER_DATE_FORMAT)

```
此外，如果是flask的日志记录的话，需要添加部分配置才能保证只初始化一次：
```
def init_logger(config):
    # 日志系统配置
    logging.basicConfig(level=config.FLASK_LOGGER_LEVEL, format=config.FLASK_LOGGER_FORMAT, datefmt=config.FLASK_LOGGER_DATE_FORMAT)
    handler = TimedRotatingFileHandler(filename=config.FLASK_LOGGER_FILE+'info.log', when="D", interval=1, backupCount=7,encoding=config.FLASK_LOGGER_CHARSET)

    formatter = logging.Formatter(config.FLASK_LOGGER_FORMAT)
    handler.setFormatter(formatter)
    handler.setLevel(config.FLASK_LOGGER_LEVEL)

    app.logger.handlers.clear()
    app.logger.addHandler(handler)

#保证不管是否是debug模式,flask启动都只执行一次
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    init_logger(config)
```
接下来就是见证奇迹的时刻，动起来吧！

###### 如果需要交流，请联系我(ps:github有常用邮箱)
