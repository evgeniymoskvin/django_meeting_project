from django.contrib.auth.forms import AuthenticationForm, UsernameField, UserCreationForm
from django.forms import ModelForm, TextInput, Textarea, CheckboxInput, Select, PasswordInput
from django.contrib.auth.models import User
from django import forms


class LoginForm(AuthenticationForm):
    username = UsernameField(
        widget=forms.TextInput(
            attrs={"autofocus": True, "class": "form-control", 'id': 'floatingInput', 'placeholder': 'Login'}))
    password = forms.CharField(
        label=("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "form-control", 'id': 'floatingPassword',
                   'placeholder': 'Password'}),
    )


class SignUpForm(UserCreationForm):
    username = UsernameField(
        widget=forms.TextInput(
            attrs={"autofocus": True, "class": "form-control", 'id': 'floatingInput', 'placeholder': 'Login'}))
    password1 = forms.CharField(
        label=("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "form-control", 'id': 'floatingPassword',
                   'placeholder': 'Password'}))
    password2 = forms.CharField(
        label=("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "form-control", 'id': 'floatingPassword',
                   'placeholder': 'Password'})

    )
    # first_name = forms.CharField(max_length=30, required=False)
    # last_name = forms.CharField(max_length=30, required=False)
    #
    # class Vena:
    #     model = User
    #     fields = ['username', 'password']
    pass