import requests
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from . import forms
from django.contrib.auth import login
from .access import get_allowed_user

import secrets
import hashlib
import base64

import jwt
from jwt import PyJWKClient

from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme

# Create your views here.
class UserLoginView(LoginView):
    form_class = forms.LoginForm
    template_name = "login/login.html"


class SignUpView(CreateView):
    form_class = forms.SignUpForm
    success_url = reverse_lazy("login")
    template_name = 'login/signup.html'


def oidc_login(request):
    request.session["oidc_next"] = request.GET.get("next", "/")

    # Генерируем PKCE verifier
    code_verifier = secrets.token_urlsafe(64)

    # Вычисляем S256 challenge
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    # Генерируем state и nonce
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Сохраняем временные значения в сессии клиента
    request.session["oidc_code_verifier"] = code_verifier
    request.session["oidc_state"] = state
    request.session["oidc_nonce"] = nonce

    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scope": " ".join(settings.OIDC_SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "nonce": nonce,
    }

    authorization_url = (
        f"{settings.OIDC_AUTHORITY}/authorize/?"
        f"{urlencode(params)}"
    )

    return redirect(authorization_url)


def oidc_callback(request):
    # Проверяем ошибки, пришедшие от Auth Service
    if request.GET.get("error"):
        return HttpResponse(
            f"Ошибка авторизации: {request.GET.get('error_description', request.GET['error'])}",
            status=400,
        )

    # Проверяем state
    state = request.GET.get("state")
    expected_state = request.session.get("oidc_state")

    if not state or state != expected_state:
        return HttpResponse(
            f"State check failed. "
            f"Received: {bool(state)}. "
            f"Expected in session: {bool(expected_state)}. "
            f"Session key: {request.session.session_key}",
            status=400,
        )

    request.session.pop("oidc_state", None)

    # Получаем authorization code
    code = request.GET.get("code")
    if not code:
        return HttpResponse("Authorization code отсутствует", status=400)

    # Получаем PKCE verifier
    code_verifier = request.session.pop("oidc_code_verifier", None)
    if not code_verifier:
        return HttpResponse("PKCE code_verifier отсутствует", status=400)

    # Получаем OIDC Discovery
    discovery_url = (
        f"{settings.OIDC_AUTHORITY}/.well-known/openid-configuration"
    )

    try:
        discovery_response = requests.get(discovery_url, timeout=10)
        discovery_response.raise_for_status()
        discovery = discovery_response.json()

        # Обмениваем authorization code на токены
        token_response = requests.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OIDC_REDIRECT_URI,
                "client_id": settings.OIDC_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=10,
        )
        token_response.raise_for_status()
        tokens = token_response.json()
        id_token = tokens.get("id_token")
        if not id_token:
            return HttpResponse("Auth Service не вернул ID Token", status=400)

        expected_nonce = request.session.pop("oidc_nonce", None)
        if not expected_nonce:
            return HttpResponse("OIDC nonce отсутствует", status=400)

        try:
            claims = validate_oidc_id_token(
                id_token,
                discovery,
                expected_nonce,
            )
        except jwt.PyJWTError:
            return HttpResponse("Проверка подписи или claims ID Token не пройдена", status=400)
        except ValueError as error:
            return HttpResponse(str(error), status=400)


    except requests.HTTPError as error:

        response = error.response

        return HttpResponse(

            f"Ошибка token endpoint. "

            f"HTTP status: {response.status_code}. "

            f"Ответ Auth Service: {response.text}",

            status=502,

        )


    except requests.RequestException as error:

        return HttpResponse(

            f"Ошибка соединения с Auth Service: {error}",

            status=502,

        )

    user = get_allowed_user(claims["sub"])

    if user is None:
        return HttpResponse(
            "Доступ запрещён. Учётная запись неактивна "
            "или сотрудник не найден/не работает.",
            status=403,
        )

    login(request, user)

    next_url = request.session.pop("oidc_next", "/")
    if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
    ):
        next_url = "/"

    return redirect(next_url)


def oidc_logout(request):
    request.session.pop("oidc_code_verifier", None)
    request.session.pop("oidc_state", None)
    request.session.pop("oidc_nonce", None)

    return redirect("login")



def validate_oidc_id_token(id_token, discovery, expected_nonce):
    jwks_client = PyJWKClient(discovery["jwks_uri"])

    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.OIDC_CLIENT_ID,
        issuer=discovery["issuer"],
        options={
            "require": ["exp", "iat", "iss", "aud", "sub", "nonce"],
        },
    )

    if claims.get("nonce") != expected_nonce:
        raise ValueError("OIDC nonce не совпадает")

    return claims

# http://localhost:8001/login/oidc/