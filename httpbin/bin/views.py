from io import BytesIO
from PIL import Image

from django.shortcuts import render
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
    HttpResponseRedirect,
    HttpResponseBadRequest,
    StreamingHttpResponse,
)
from django.core import serializers
from django.urls import reverse
from django.template import loader
from django.views.decorators.gzip import gzip_page

from urllib.parse import unquote
import itertools
import hashlib
import json
import zlib
import random
import base64

from .helpers import methods, get_headers, no_get

JSON_FORMAT = {
    "indent": 2,
    "sort_keys": True,
}


@methods(["GET", "HEAD", "OPTIONS"])
def home(request):
    return render(request, "bin/index.html")


@methods(["GET", "HEAD", "OPTIONS"])
def ip(request):
    ip = request.META["REMOTE_ADDR"]
    return JsonResponse({"origin": ip}, json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def user_agent(request):
    user_agent = request.META["HTTP_USER_AGENT"]
    return JsonResponse({"user-agent": user_agent}, json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def headers(request):
    headers = get_headers(request)
    return JsonResponse({"headers": headers}, json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def get(request):
    rep_dict = {
        "args": request.GET,
        "headers": get_headers(request),
        "origin": request.META["REMOTE_ADDR"],
        "url": request.build_absolute_uri(),
    }
    return JsonResponse(rep_dict, json_dumps_params=JSON_FORMAT)


@methods(["POST", "HEAD", "OPTIONS"])
def post(request):
    return JsonResponse(no_get(request), json_dumps_params=JSON_FORMAT)


@methods(["PATCH", "HEAD", "OPTIONS"])
def patch(request):
    return JsonResponse(no_get(request), json_dumps_params=JSON_FORMAT)


@methods(["PUT", "HEAD", "OPTIONS"])
def put(request):
    return JsonResponse(no_get(request), json_dumps_params=JSON_FORMAT)


@methods(["DELETE", "HEAD", "OPTIONS"])
def delete(request):
    return JsonResponse(no_get(request), json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def utf8(request):
    return JsonResponse(no_get(request), json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
@gzip_page
def gzip(request):
    rep_dict = {
        "deflated": True,
        "headers": get_headers(request),
        "method": request.method,
        "origin": request.META["REMOTE_ADDR"],
    }
    return JsonResponse(rep_dict, json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def deflate(request):
    rep_dict = {
        "deflated": True,
        "headers": get_headers(request),
        "method": request.method,
        "origin": request.META["REMOTE_ADDR"],
    }
    # 2-byte zlib header and 4-byte checksum
    data = zlib.compress(json.dumps(rep_dict, **JSON_FORMAT).encode("utf-8"))[2:-4]
    rep = HttpResponse(data, content_type="application/json")
    rep["Content-Encoding"] = "deflate"
    rep["Content-Length"] = len(data)
    return rep


@methods(["GET", "HEAD", "OPTIONS"])
def status(request, code):
    code = random.choice(code.split(","))
    if code == "418":
        rep = HttpResponse(status=int(code), reason="I'M A TEAPOT")
        rep.content = loader.render_to_string("bin/418.html", request=request)
        del rep["content-type"]
        return rep
    return HttpResponse(status=int(code))


@methods(["GET", "HEAD", "OPTIONS"])
def response_headers(request):
    rep = HttpResponse(content_type="application/json")
    headers = {k: v for k, v in rep.items()}
    headers["Content-Length"] = ""
    if request.META["QUERY_STRING"]:
        query_string_list = [
            qs.split("=", 1) for qs in unquote(request.META["QUERY_STRING"]).split("&")
        ]
        for k, v in query_string_list:
            rep[k] = v
            if k not in headers:
                headers[k] = v
            else:
                if isinstance(headers[k], list):
                    headers[k].append(v)
                else:
                    headers[k] = [headers[k], v]
    length = len(json.dumps(headers, **JSON_FORMAT))
    headers["Content-Length"] = str(length + len(str(length)))
    rep["Content-Length"] = headers["Content-Length"]
    rep.content = json.dumps(headers, **JSON_FORMAT)
    return rep


@methods(["GET", "HEAD", "OPTIONS"])
def redirect(request, times):
    if times == "1":
        return HttpResponseRedirect(reverse("get"))
    else:
        return HttpResponseRedirect(reverse("redirect", args=[int(times) - 1]))


@methods(["GET", "HEAD", "OPTIONS"])
def redirect_to(request):
    if "url" in request.GET:
        if "status_code" in request.GET:
            return HttpResponseRedirect(
                request.GET["url"], status=int(request.GET["status_code"])
            )
        else:
            return HttpResponseRedirect(request.GET["url"])
    else:
        return HttpResponseBadRequest()


@methods(["GET", "HEAD", "OPTIONS"])
def relative_redirect(request, times):
    if times == "1":
        return HttpResponseRedirect(reverse("get"))
    else:
        return HttpResponseRedirect(reverse("relative-redirect", args=[int(times) - 1]))


@methods(["GET", "HEAD", "OPTIONS"])
def absolute_redirect(request, times):
    if times == "1":
        return HttpResponseRedirect(request.build_absolute_uri("/get"))
    else:
        return HttpResponseRedirect(
            "%s/%d" % (request.build_absolute_uri("/absolute-redirect"), int(times) - 1)
        )


@methods(["GET", "HEAD", "OPTIONS"])
def cookies(request):
    return JsonResponse({"cookies": request.COOKIES}, json_dumps_params=JSON_FORMAT)


@methods(["GET", "HEAD", "OPTIONS"])
def cookies_set(request):
    res = HttpResponseRedirect(reverse("cookies"))
    for key, value in request.GET.items():
        res.set_cookie(key, value)
    return res


@methods(["GET", "HEAD", "OPTIONS"])
def cookies_delete(request):
    res = HttpResponseRedirect(reverse("cookies"))
    for key in request.GET.keys():
        res.delete_cookie(key)
    return res


@methods(["GET", "HEAD", "OPTIONS"])
def basic_auth(requeset, user, passwd):
    if "HTTP_AUTHORIZATION" in requeset.META:
        auth = requeset.META["HTTP_AUTHORIZATION"].split()
        if auth[0] == "Basic":
            auth_str = base64.b64decode(auth[1]).decode("utf-8")
            username, password = auth_str.split(":", 1)
            if username == user and password == passwd:
                rep_dict = {"authenticated": True, "user": user}
                return JsonResponse(rep_dict, json_dumps_params=JSON_FORMAT)

    rep = HttpResponse(status=401)
    rep["WWW-Authenticate"] = "Basic realm='basic auth'"
    return rep


@methods(["GET", "HEAD", "OPTIONS"])
def hidden_basic_auth(request, user, passwd):
    if "HTTP_AUTHORIZATION" in request.META:
        auth = requeset.META["HTTP_AUTHORIZATION"].split()
        if auth[0] == "Basic":
            auth_str = base64.b64decode(auth[1]).decode("utf-8")
            username, password = base64.b64decode(auth_str).split(":", 1)
            if username == user and password == passwd:
                rep_dict = {"authenticated": True, "user": user}
                return JsonResponse(rep_dict, json_dumps_params=JSON_FORMAT)
    else:
        return HttpResponse(status=404)


def md5(content):
    md = hashlib.new("md5")
    md.update(content.encode("utf-8"))
    return md.hexdigest()


@methods(["GET", "HEAD", "OPTIONS"])
def digest_auth(request, qop, user, passwd, algorithm):
    if qop not in ["auth", "auth-int"]:
        qop = "auth, auth-int"

    if "HTTP_AUTHORIZATION" in request.META:
        auth = request.META["HTTP_AUTHORIZATION"].split(" ", 1)
        if auth[0] == "Digest":
            info_dict = {
                kv_list[0].strip(): kv_list[1].strip('"')
                for kv_list in [kv_str.split("=") for kv_str in auth[1].split(",")]
            }
            if info_dict["username"] == user:
                ha1 = md5(
                    "{user}:{realm}:{passwd}".format(
                        user=user, realm=info_dict["realm"], passwd=passwd
                    )
                )
                ha2 = md5(
                    "{method}:{uri}".format(method=request.method, uri=info_dict["uri"])
                )
                response = md5(
                    "{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".format(
                        ha1=ha1,
                        nonce=info_dict["nonce"],
                        nc=info_dict["nc"],
                        cnonce=info_dict["cnonce"],
                        qop=info_dict["qop"],
                        ha2=ha2,
                    )
                )
                if response == info_dict["response"]:
                    rep_dict = {"authenticated": True, "user": user}
                    return JsonResponse(rep_dict, json_dumps_params=JSON_FORMAT)

    rep = HttpResponse(status=401)
    rep["WWW-Authenticate"] = (
        'Digest realm="%s", qop="%s", nonce="%s", opaque="%s", algorithm=%s'
        % ("digest", qop, "5", "5", algorithm)
    )
    return rep


@methods(["GET", "HEAD", "OPTIONS"])
def download(request):
    size = int(request.GET.get("filesize", 1024))
    response = StreamingHttpResponse((b" " for _ in range(size)))
    response.headers["Content-Length"] = size
    response.headers["Content-Disposition"] = (
        'attachment; filename="file-%s.txt"' % size
    )
    response.headers["Content-Type"] = "application/octet-stream"
    return response


def image(request):
    try:
        w = int(request.GET.get("w", 64))
    except:
        w = 64

    try:
        h = int(request.GET.get("h", 64))
    except:
        h = 64

    w = min(w, 1024)
    h = min(h, 1024)

    img = Image.effect_mandelbrot((w, h), (-3, -2.5, 2, 2.5), 10)
    buf = BytesIO()

    format = request.GET.get("format", "png")
    content_type = "image/png"

    if format != "png":
        format = "jpeg"
        content_type = "image/jpeg"

    img.save(buf, format)
    buf.seek(0)

    return HttpResponse(buf, content_type=content_type)


def ogp(request):
    return render(request, "bin/ogp.html")


def echo(request):
    return HttpResponse(
        request.body,
        content_type=request.META.get("CONTENT_TYPE", "application/json"),
    )
