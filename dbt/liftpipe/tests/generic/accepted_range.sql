{#
    Fails for rows where the column falls outside [min_value, max_value].
    Nulls pass; combine with not_null where a value is required.
#}
{% test accepted_range(model, column_name, min_value=none, max_value=none) %}

select {{ column_name }} as offending_value
from {{ model }}
where {{ column_name }} is not null
  and (
    false
    {% if min_value is not none %} or {{ column_name }} < {{ min_value }} {% endif %}
    {% if max_value is not none %} or {{ column_name }} > {{ max_value }} {% endif %}
  )

{% endtest %}
