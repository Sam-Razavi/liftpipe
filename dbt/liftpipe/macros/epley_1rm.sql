{#
    Estimated one-rep max (Epley, 1985): weight * (1 + reps / 30).
    Only meaningful for loaded sets of 1-12 reps; returns null otherwise.
    A single rep returns the weight itself.
#}
{% macro epley_1rm(weight, reps) -%}
    case
        when {{ weight }} > 0 and {{ reps }} = 1 then {{ weight }}
        when {{ weight }} > 0 and {{ reps }} between 2 and 12
            then round({{ weight }} * (1 + {{ reps }} / 30.0), 2)
    end
{%- endmacro %}
