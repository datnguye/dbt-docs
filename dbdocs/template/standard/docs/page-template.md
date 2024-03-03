# {{ model_id }}

**📓 Description:**
{{ model_description }}

**🏷️ Tags:**
{{ model_tags }}

**🔗 References:**

```mermaid
{{ model_erd }}
```

<details open>
  <summary> <b>Fields ({{ column_count }})</b> </summary>


| Name          | Type            |  Tags            |  Description                                |
|---------------|-----------------|------------------|---------------------------------------------|
{% for column in columns -%}
| {{ column.name }} | {{ column.type }} | {{ column.tags }} | {{ column.description }} |
{%- endfor %}

</details>
