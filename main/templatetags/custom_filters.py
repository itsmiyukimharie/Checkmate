from django import template
import json

register = template.Library()

@register.filter
def range_filter(value, start=1):
    """
    Generate a range of numbers from start to value+start
    Usage: {{ question_count|range_filter:1 }}
    """
    try:
        return range(start, int(value) + start)
    except (ValueError, TypeError):
        return range(0)

@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key, handling both string and integer keys
    Usage: {{ dict|get_item:key }}
    """
    try:
        if hasattr(dictionary, 'get'):
            # Try the key as-is first
            result = dictionary.get(key)
            if result is not None:
                return result
            
            # If key is int, try as string
            if isinstance(key, int):
                result = dictionary.get(str(key))
                if result is not None:
                    return result
            
            # If key is string, try as int
            if isinstance(key, str) and key.isdigit():
                result = dictionary.get(int(key))
                if result is not None:
                    return result
                    
        elif hasattr(dictionary, '__getitem__'):
            # Try direct access
            try:
                return dictionary[key]
            except KeyError:
                # Try alternative key type
                if isinstance(key, int):
                    return dictionary[str(key)]
                elif isinstance(key, str) and key.isdigit():
                    return dictionary[int(key)]
        
        return None
    except (AttributeError, TypeError, KeyError, ValueError):
        return None

@register.filter
def multiply(value, arg):
    """
    Multiply value by arg
    Usage: {{ value|multiply:2 }}
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value):
    """
    Convert decimal to percentage
    Usage: {{ 0.85|percentage }}
    """
    try:
        return f"{float(value) * 100:.0f}%"
    except (ValueError, TypeError):
        return "0%"

@register.filter
def pprint(value):
    """
    Pretty print for debugging
    Usage: {{ dict|pprint }}
    """
    try:
        return json.dumps(value, indent=2)
    except:
        return str(value)