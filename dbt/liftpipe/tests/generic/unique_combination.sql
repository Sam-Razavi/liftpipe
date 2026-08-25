{# Fails when a combination of columns is not unique (a composite grain check). #}
{% test unique_combination(model, columns) %}

select {{ columns | join(', ') }}, count(*) as occurrences
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
