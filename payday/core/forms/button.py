from django.utils.safestring import mark_safe
from typing import Optional, Dict, Any, List
from django.utils.text import slugify

class Button:
    """
    A flexible Button class for Django that can render different HTML tags (a, button, input).
    Always includes 'btn' class and appends additional classes.
    
    Attributes:
        text (str): The text to display on the button
        tag (str): HTML tag to use ('a', 'button', 'input')
        url (Optional[str]): The URL for link tags (required for 'a' tags)
        classes (str): Additional CSS classes to append after 'btn'
        attrs (Optional[Dict[str, Any]]): Additional HTML attributes
        is_disabled (bool): Whether the button should be disabled
        permission (Optional[str]): Permission required to render the button
        dropdown (Optional[List['Button']]): List of dropdown buttons
    """
    
    VALID_TAGS = ['a', 'button', 'input']
    
    def __init__(
        self,
        text: str,
        tag: str = 'button',
        url: Optional[str] = None,
        classes: str = '',
        attrs: Optional[Dict[str, Any]] = None,
        is_disabled: bool = False,
        permission: Optional[str] = None,
        dropdown: Optional[List['Button']] = None,
    ):
        self.text = text
        self.tag = tag.lower()
        self.url = url
        self.classes = classes
        self.attrs = attrs or {}
        self.is_disabled = is_disabled
        self.permission = permission
        self.dropdown = dropdown or []

        self._validate_tag()
        self._validate_url()

    def _validate_tag(self) -> None:
        """Validate the HTML tag."""
        if self.tag not in self.VALID_TAGS:
            raise ValueError(f"tag must be one of {', '.join(self.VALID_TAGS)}")

    def _validate_url(self) -> None:
        """Validate the URL for anchor tags."""
        if self.tag == 'a' and not self.url:
            raise ValueError("URL is required for anchor tags")
    
    def get_classes(self) -> str:
        """Combine default and additional classes."""
        all_classes = []
        
        if self.classes:
            all_classes.extend(self.classes.split())
            
        if 'class' in self.attrs:
            attr_classes = self.attrs.pop('class').split()
            all_classes.extend(attr_classes)
            
        return ' '.join(all_classes)
    
    def generate_id(self) -> str:
        """Generate a unique ID for the button."""
        return f"{self.tag}_{slugify(self.text)}"

    def get_attrs_string(self) -> str:
        """Convert attributes dictionary to HTML attribute string."""
        attrs = self.attrs.copy()
        attrs['class'] = self.get_classes()
        
        if self.is_disabled:
            self._handle_disabled_state(attrs)
        
        if self.tag == 'a':
            attrs['href'] = self.url
            attrs['role'] = 'button'
        
        if self.tag == 'input':
            attrs['type'] = attrs.get('type', 'submit')
            attrs['value'] = self.text
        
        if 'id' not in attrs:
            attrs['id'] = self.generate_id()

        if self.dropdown:
            self._add_dropdown_attrs(attrs)

        return ' '.join([f'{key}="{value}"' for key, value in attrs.items()])

    def _handle_disabled_state(self, attrs: Dict[str, Any]) -> None:
        """Handle disabled state for different tags."""
        if self.tag == 'a':
            attrs['tabindex'] = '-1'
            attrs['aria-disabled'] = 'true'
        else:
            attrs['disabled'] = 'disabled'
    
    def _add_dropdown_attrs(self, attrs: Dict[str, Any]) -> None:
        """Add attributes for dropdown functionality."""
        attrs['data-toggle'] = 'dropdown'
        attrs['aria-haspopup'] = 'true'
        attrs['aria-expanded'] = 'false'
        attrs['data-bs-toggle'] = 'dropdown'
        
        # Add dropdown-toggle class
        if 'class' in attrs:
            attrs['class'] += ' dropdown-toggle'
        else:
            attrs['class'] = 'dropdown-toggle'

    def render(self) -> str:
        """Render the button as HTML."""
        attrs_string = self.get_attrs_string()
        
        if self.tag == 'input':
            html = f'<input {attrs_string} />'
        elif self.tag == 'a':
            html = f'<a {attrs_string}>{self.text}</a>'
        else:
            html = f'<button {attrs_string}>{self.text}</button>'
        
        if self.dropdown:
            _id = self.attrs.get('id', self.generate_id())
            dropdown_html = ''.join([button.render() for button in self.dropdown])
            html += f'<div class="dropdown-menu" aria-labelledby="{_id}">{dropdown_html}</div>'
            html = f'<span>{html}</span>'
        
        return mark_safe(html)
    
    def __str__(self) -> str:
        return self.render()
