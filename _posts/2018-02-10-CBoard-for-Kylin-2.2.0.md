---
layout: post
title:  "CBoard-0.4分支对kylin-2.2.0的支持"
categories: CBoard
tags: CBoard Kylin 兼容
author: Victor
---

* content
{:toc}


<p>
最近要研究Kylin的操作与使用，看中它的预处理能力和查询卓越的性能。于是便有了找个开源BI系统的来可视化Kylin查询的诉求。使用过superset-kylin，但是由于某些bug还是不得不放弃。在github上找到一款国产的BI工具，使用和配置还比较简便，Java开发也算对口，于是试着搭建试用下。bug总是有的，CBoard默认下载分支为0.4,部署完成后，发现0.4对于Kylin-2.2.0的兼容性很差，数据源添加和查询都没法进行(当然，官方回复我说0.5分支才支持Kylin-2.*版本，然后并没有事先说明-_-)。
</p>
于是乎，下载源码开始自己改咯。追踪发现，是有关Kylin API的调用规则和返回结果的格式改了，0.4版本无法解析造成了,而且还得模拟Kylin中c代码类型的转化。于是乎，开改咯  
<!-- more -->
```
private Map<String, String> getColumnsType(Map<String, String> query, String table, String serverIp, String username, String password) {
        RestTemplate restTemplate = new RestTemplate();
        restTemplate.getInterceptors().add(new BasicAuthorizationInterceptor(username, password));
        ResponseEntity<String> a = restTemplate.getForEntity("http://" + serverIp + "/kylin/api/tables_and_columns?project=" + query.get(PROJECT), String.class);
//        ResponseEntity<String> a = restTemplate.getForEntity("http://" + serverIp + "/kylin/api/tables/{tableName}", String.class, table);
        Map<String, String> result = new HashedMap();
        JSONArray jsonArray = JSON.parseArray(a.getBody());
        for (int i = 0; i < jsonArray.size(); i++) {
            JSONObject tableObject = (JSONObject) jsonArray.get(i);
            if (!table.equals(tableObject.get("table_SCHEM")+"."+tableObject.get("table_NAME")))
                continue;
            tableObject.getJSONArray("columns").stream().map(e -> (JSONObject) e).forEach(e -> result.put(e.getString("column_NAME"), getType(e.getInteger("data_TYPE"))));
        }
//        JSONObject jsonObject = JSONObject.parseObject(a.getBody());
//        jsonObject.getJSONArray("columns").stream().map(e -> (JSONObject) e).forEach(e -> result.put(e.getString("name"), e.getString("datatype")));
        return result;
    }
```
```
    public KylinModel(Map<String, String> query, JSONObject model, String serverIp, String username, String password) throws Exception {
        if (model == null) {
            throw new CBoardException("Model not found");
        }
        this.model = model;
        String t = ((JSONObject) model).getString("fact_table");
        model.getJSONArray("dimensions").forEach(e -> {
//                    String t = ((JSONObject) e).getString("table");
                    Map<String, String> types = getColumnsType(query, t, serverIp, username, password);
                    types.entrySet().forEach(et -> columnType.put(et.getKey(), et.getValue()));
                    ((JSONObject) e).getJSONArray("columns").stream().map(c -> c.toString()).forEach(s -> {
                                String alias = tableAlias.get(t);
                                if (alias == null) {
                                    alias = "_t" + tableAlias.keySet().size() + 1;
                                    tableAlias.put(t, alias);
                                }
                                columnTable.put(s, t);
                            }
                    );
                }
        );
        model.getJSONArray("metrics").stream().map(e -> e.toString()).forEach(s ->
                {
//                    String t = model.getString("fact_table");
                    String alias = tableAlias.get(t);
                    if (alias == null) {
                        alias = "_t" + tableAlias.keySet().size() + 1;
                        tableAlias.put(t, alias);
                    }
                    columnTable.put(s, t);
                }
        );
    }
```
其中，注释部分为被更改项<br>
最后是对类型的转换关系
```
public enum TypeEnum {

    BIT(-7, "BIT"), TINYINT(-6, "TINYINT"), SMALLINT(5, "SMALLINT"), INTEGER(4, "INTEGER"), BIGINT(-5, "BIGINT"), FLOAT(6, "FLOAT"), REAL(7, "REAL"), DOUBLE(8, "DOUBLE"), NUMERIC(2, "NUMERIC"),
    DECIMAL(3, "DECIMAL"), CHAR(1, "CHAR"), VARCHAR(12, "VARCHAR"), LONGVARCHAR(-1, "LONGVARCHAR"), DATE(91, "DATE"), TIME(92, "TIME"), TIMESTAMP(93, "TIMESTAMP"), BINARY(-2, "BINARY"), VARBINARY(-3, "VARBINARY"), LONGVARBINARY(-4, "LONGVARBINARY");

    private Integer index;
    private String name;

    private TypeEnum(Integer index, String name) {
        this.name = name;
        this.index = index;
    }

    public Integer getIndex() {
        return index;
    }

    public void setIndex(Integer index) {
        this.index = index;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }
}

private String getType(Integer index) {
        String name = null;
        for (TypeEnum s : TypeEnum.values()) {
            if (!index.equals(s.getIndex()))
                continue;
            name = s.getName();
            break;
        }
        return name;
    }
```
Mission complete！