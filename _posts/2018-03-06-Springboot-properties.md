---
layout: post
title:  "Springboot执行方式不同解析Properties差异"
categories: Springboot
tags: Springboot 解析 Properties
author: Victor
---

* content
{:toc}


<p>
在
springboot中，经常会出现采用jar执行还是丢到tomcat中执行的情况，下面就是会有差异的部分
</p>
<p>
对于通过jar包导入到tomcat等容器的方式，spring会执行直接在classpath下面找到对应的文件夹加载文件,类似下面的代码
</p>>
```
 this.dirPath = (new DefaultResourceLoader()).getResource("classpath:" + dirPath).getURI().getPath();
    File dir = new File(this.dirPath);
    if(!dir.isDirectory()) {
        throw new FileNotFoundException(dir + " does not exist");
    }
    initTemplateData(dir);
```
一旦是通过jar包方式执行的，那就会出现找不到对应的classpath目录下的指定文件，那么就需要对springboot特有的jar文件解析成特定的格式

```
// 找到!/ 截断之前的字符串
String jarPath = urlStr.substring(0, urlStr.lastIndexOf("!/") + 2);
URL jarURL = new URL(jarPath);
JarURLConnection jarCon = (JarURLConnection) jarURL.openConnection();
JarFile jarFile = jarCon.getJarFile();
Enumeration<JarEntry> jarEntrys = jarFile.entries();
Properties props = null;
while (jarEntrys.hasMoreElements()) {
    JarEntry entry = jarEntrys.nextElement();
    String name = entry.getName();
    if (name.startsWith(dirPath) && !entry.isDirectory()) {
    .............
    }
}
```
同时，如果想保证加载的Properties文件中的内容保持之前的顺序，必须实现对properties类的重写

```
public class OrderedProperties extends Properties {
    private static final long serialVersionUID = -1;

    private final LinkedHashSet<Object> keys = new LinkedHashSet<Object>();

    public Enumeration<Object> keys() {
        return Collections.<Object> enumeration(keys);
    }

    public Object put(Object key, Object value) {
        keys.add(key);
        return super.put(key, value);
    }

    public Set<Object> keySet() {
        return keys;
    }

    public Set<String> stringPropertyNames() {
        Set<String> set = new LinkedHashSet<String>();

        for (Object key : this.keys) {
            set.add((String) key);
        }

        return set;
    }
}
```
这样才能保证加载有序。
完整的加载springboot不同解析方式的代码大致如下:

```
public TableTemplateGenerator(String dirPath) throws IOException {
        ClassLoader classLoader = getClass().getClassLoader();
        URL url = classLoader.getResource(dirPath);
        String urlStr = url.toString();
        if(urlStr.contains("!/")){
            // 找到!/ 截断之前的字符串
            String jarPath = urlStr.substring(0, urlStr.lastIndexOf("!/") + 2);
            URL jarURL = new URL(jarPath);
            JarURLConnection jarCon = (JarURLConnection) jarURL.openConnection();
            JarFile jarFile = jarCon.getJarFile();
            Enumeration<JarEntry> jarEntrys = jarFile.entries();
            Properties props = null;
            while (jarEntrys.hasMoreElements()) {
                JarEntry entry = jarEntrys.nextElement();
                String name = entry.getName();
                if (name.startsWith(dirPath) && !entry.isDirectory()) {
                    String fileName = name.split("/")[1].split("\\.")[0];
                    props = new OrderedProperties();
                    InputStream is = this.getClass().getClassLoader().getResourceAsStream(name);
                    props.load(new InputStreamReader(is, "UTF-8"));
                    List<String> keys = new ArrayList<>();
                    List<String[]> headers = new ArrayList<>();
                    for (Object key : props.keySet()) {
                        String value = props.get(key).toString();
                        keys.add(key.toString());
                        headers.add(new String[]{key.toString(), value});
                    }
                    TableData tableData = new TableData();
                    tableData.setCnHeaders(headers);
                    tableData.setKeys(keys);
                    tableDataMap.put(fileName, tableData);;
                }
            }
        }else{
            this.dirPath = (new DefaultResourceLoader()).getResource("classpath:" + dirPath).getURI().getPath();
            File dir = new File(this.dirPath);
            if(!dir.isDirectory()) {
                throw new FileNotFoundException(dir + " does not exist");
            }
            initTemplateData(dir);
        }
    }
```
