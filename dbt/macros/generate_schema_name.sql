{# dbt's default behaviour concatenates the target schema with a model's
   custom +schema config (e.g. "main_gold" instead of "gold"). Overriding to
   use the custom schema name exactly as given, so raw/silver/gold stay
   clean schema names matching docs/architecture.md and existing queries. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
