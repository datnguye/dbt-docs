# {{ model_id }}

📓 {{ model_description }}

> **tags**: {{ model_tags }}

## 📖 Definition

| Name          | Type            |  Tags            |  Description                                |
|---------------|-----------------|------------------|---------------------------------------------|
{% for column in columns -%}
| {{ column.get("name") }} | {{ column.get("type") }} | {{ column.get("tags") }} | {{ column.get("description") }} |
{% endfor %}

## 🔗 References

```mermaid
{{ model_erd }}
```
