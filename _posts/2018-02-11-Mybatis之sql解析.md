---
layout: post
title:  "Mybatis解析Node成完整Sql"
categories: Mybatis
tags: Mybatis 解析 Sql
author: Victor
---

* content
{:toc}

<p>
都是为了优化，所以走上了配置化道路，sql代替代码实现逻辑，so，有了这个补丁。来一波Mybatis解析sql的代码来装下过年的气氛，*_*
</p>

```
public String kylinSql(String content, Map<String, Object> param) {
        Configuration configuration = sqlSessionTemplate.getConfiguration();
        Document doc = DOMUtils.parseXMLDocument(content);
        XPathParser xPathParser = new XPathParser(doc, false);
        Node node = doc.getFirstChild();
        XNode xNode = new XNode(xPathParser, node, null);
        XMLScriptBuilder xmlScriptBuilder = new XMLScriptBuilder(configuration, xNode);
        SqlSource sqlSource = xmlScriptBuilder.parseScriptNode();
        MappedStatement.Builder builder = new MappedStatement.Builder(configuration, content.toString(), sqlSource, null);
        List<ResultMap> resultMaps = new ArrayList<>();
        List<ResultMapping> resultMappings = new ArrayList<>();
        ResultMap.Builder resultMapBuilder = new ResultMap.Builder(configuration, content.toString(), Map.class, resultMappings, true);
        resultMaps.add(resultMapBuilder.build());
        MappedStatement ms = builder.resultMaps(resultMaps).build();
        BoundSql boundSql = ms.getBoundSql(param);
        List<ParameterMapping> parameterMappings= boundSql.getParameterMappings();
        Map<String,Object> objectMap =  (Map)boundSql.getParameterObject();
        String resultSql = boundSql.getSql();
        for(ParameterMapping mapping : parameterMappings){
            if(boundSql.getAdditionalParameter(mapping.getProperty())==null){
                resultSql = resultSql.replaceFirst("[?]",objectMap.get(mapping.getProperty()).toString());
                continue;
            }
            resultSql = resultSql.replaceFirst("[?]", boundSql.getAdditionalParameter(mapping.getProperty()).toString());
        }
        System.out.println("最终sql为: "+ resultSql);
        return resultSql;
    }
```
更多福利需要的欢迎issue，春节快乐！
Mission complete！