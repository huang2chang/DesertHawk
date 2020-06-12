#from captcha.models import CaptchaStore
import hashlib
import json
import socket
import struct
import urllib
from urllib.parse import urlencode

from django.contrib.auth import logout,login,authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Q, QuerySet
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse

from apps.user.models import VisitUser

def set_cookie(request):
    obj = HttpResponse('ok')    #obj=render(request,...)
    obj.set_cookie('name', 'ABC')
    # obj.set_signed_cookie(key,value,salt='加密盐')
    obj.set_signed_cookie('name', 'lqz', salt='123')#加盐,123是个密码,解cookie的时候需要它,
    return obj


def login(request):
    response = dict()
    response["status"] = "success"
    response["msg"] = "成功"
    response["user"] = dict()

    phone = request.POST.get("phone", None)
    password = request.POST.get("password", None)

    phone = '15692097691'
    password = '123456'

    if not phone or not password:
        response["status"] = "error"
        response["msg"] = "密码或用户名为空"
        return HttpResponse(json.dumps(response), content_type="application/json")

    s1 = hashlib.sha1()
    s1.update(password.encode("utf8"))  # 指定编码格式，否则会报错
    md5password = s1.hexdigest()

    try:
        row = VisitUser.objects.get(phone=phone, password=md5password)
        response["user"]["id"] = row.id
        response["user"]["header_url"] = row.header_url

        request.session['user_id'] = row.id
        #request.session['age'] = '18'
        request.session.set_expiry(60) #30秒后过期
        # 默认是14天后过期，0表示关闭浏览器过期

    except Exception as e:
        print(phone, password, md5password, e)
        response["status"] = "error"
        response["msg"] = "用户名或密码错误"
        return HttpResponse(json.dumps(response), content_type="application/json")

    return HttpResponse(json.dumps(response), content_type="application/json")

#用户注册
def regist(request):
    if request.method == 'GET':
        return render(request, 'templates/register.html')
    if request.method == "POST":
        #return render(request, 'register.html', context={'msg': '注册成功，即将跳转到登陆页面', 'yes': 1})

        username = request.POST.get("username")
        password = request.POST.get('password1')
        phone = request.POST.get('phone')

        if VisitUser.objects.filter(username=username).exists():
            return render(request, 'templates/register.html', context={'msg': '该用户名已经被注册', 'yes': 0})

        if VisitUser.objects.filter(phone=phone).exists():
            return render(request, 'templates/register.html', context={'msg': '该手机号已经被注册', 'yes': 0})

        s1 = hashlib.sha1()
        s1.update(password.encode("utf8"))
        md5password = s1.hexdigest()

        VisitUser.objects.create(password=md5password, username=username, phone=phone)

        return render(request, 'templates/register.html', context={'msg': '注册成功，即将跳转到登陆页面', 'yes': 1})

        """
        username = request.POST.get('username')
        mobile =  request.POST.get('mobile')
        Password = request.POST.get('Password')
        email = request.POST.get('email')
        users = UserProfile.objects.filter(Q(username=username)|Q(mobile=mobile)).exists()
        if users:
            # return HttpResponse('注册失败')
            return render(request, 'register.html', context={'msg': '注册失败，请重新填写', 'yes':0})
        else:
            user = UserProfile()
            user.username = username
            user.mobile = mobile
            user.email = email
            user.password = make_password(Password)
            user.save()
            return render(request, 'register.html', context={'msg': '注册成功，即将跳转到登陆页面', 'yes':1})
        """


def user_login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        username = request.POST.get('username')
        users = UserProfile.objects.filter(username=username)
        if users:
            password = request.POST.get('password')
            #方式一（通用的方式）
            # if users.first().check_password(password):
            #     request.session['username'] = username
            #     return redirect(reverse('index'))
            #
            # else:
            #     return render(request, 'login.html', context={'msg':'密码错误'})

            #方式二，前提继承了Abstrack
            user = authenticate(username=username, password=password)
            if user:
                login(request, user) #将用户对象保存在底层的request中
                request.session['username'] = username
                # return render(request, 0'login.html', context={'msg':'密码错误'})
                return redirect(reverse('index'))
            else:
                return render(request, 'login.html', context={'msg':'密码错误'})

        else:
            return render(request, 'login.html', context={'msg': '用户名不存在'})


#注销账户
def user_logout(request):
    # request.session.flush()  #删除了Cookie session 缓存里的信息

    #调用函数
    logout(request)
    return redirect(reverse('index'))

def gbook(request):
    return render(request, 'gbook.html', context={'msg': '用户名不存在'})


def send_code(request):
    mobile = request.GET.get('mobile')
    user = UserProfile.objects.filter(mobile=mobile).first()
    if user:
        json_result = util_sendmsg(mobile)
        # 发送验证码，第三方
        print(mobile)
        status = json_result.get('code')
        data = {
            'status':200,
            'msg':"ok"
        }
        if status == 200:
            check_code = json_result.get('obj')
            #使用session保存
            request.session[mobile] = check_code
            data['status'] = 200
            data['msg'] = '验证码发送成功'
        else:
            data['status'] = 500
            data['msg'] = '验证码发送失败'

        return JsonResponse(data=data)

    else:
        data = {
            'status':501,
            'msg':"用户不存在"
        }
        return JsonResponse(data=data)


def code_login(request):
    if request.method == 'GET':
        return render(request, 'codelogin.html')
    elif request.method == 'POST':
        mobile = request.POST.get('rp_mobile')
        code = request.POST.get('code')

        #根据mobile去session取值
        check_code = request.session.get(mobile)
        if code == check_code:
            user = UserProfile.objects.filter(mobile=mobile).first()
            if user:
                login(request, user)
                # request.session['username'] = user.username
            return redirect(reverse('index'))
        else:
            return render(request, 'codelogin.html', context={'msg':'验证码输入有误'})


def forget_password(request):
    if request.method == 'GET':
        form = CaptchaTestForm()
        return render(request, 'forget_pwd.html', context={'form':form})
    elif request.method =='POST':
        #获取提交的邮箱， 发送邮箱，通过发送的邮箱设置新的密码
        email = request.POST.get('email')
        #给此邮箱地址发送邮件
        result =send_email(email, request)
        print(result)
        print("=" *100)
        if result == 2:
            render(result, 'update_pwd.html', context={"check":'用户名不存在'})
        if result:
            render(result, 'update_pwd.html', context={"check":'验证信息已发送至您的邮箱'})
        else:
            render(result, 'update_pwd.html', context={"check":'验证信息发送失败，请稍后再试'})



#更新密码
def update_pwd(request):
    if request.method == 'GET':
        c = request.GET.get('c')
        return render(request, 'update_pwd.html',context={'c':c})
    elif request.method == 'POST':
        code = request.POST.get('code')
        uid = request.session.get(code)
        user = UserProfile.objects.get(pk=uid)
        pwd = request.POST.get('password')
        repwd = request.POST.get('rpassword')
        if pwd == repwd and user:
            pwd = make_password(pwd)
            user.password = pwd
            user.save()
            # request.session.flush()
            return render(request, 'update_pwd.html',context={'msg':'用户名密码更新成功！'})
        else:
            return render(request, 'update_pwd.html', context={'msg': '更新失败'})


#定义一个路由验证码
def valide_code(request):
    if request.is_ajax():
        key = request.GET.get('key')
        code = request.GET.get('code')
        captche = CaptchaStore.objects.filter(hashkey=key).first()
        data = {}
        if captche.response==code.lower():
            #正确
            data['status'] = 1
            print(data)
            return JsonResponse(data=data)
        else:
            #错误
            data['status'] = 0
            print(data)
            return JsonResponse(data=data)

# @login_required  #login(request, user) user-->继承Abstract
# def user_center(request):
#     user = request.user
#     if request.method == 'GET':
#         return render(request,'center.html', context={'user':user})
#     elif request.method == 'POST':
#         username = request.POST.get('username')
#         email = request.POST.get('email')
#         mobile = request.POST.get('mobile')
#         icon = request.FILES.get('icon')   #获得的只是图片的二进制信息
#         name = icon.name
#         user.username = username
#         user.email = email
#         user.mobile = mobile
#         user.icon = icon   #利用插件直接就可以保存
#         user.save()
#
#         return render(request, 'center.html', context={'user': user})
#

#图片上传到云
@login_required
def user_center(request):
    user = request.user
    if request.method == 'GET':
        return render(request, 'center.html', context={'user': user})
    elif request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        icon = request.FILES.get('icon')  # 获得的只是图片的二进制信息
        name = icon.name
        user.username = username
        user.email = email
        user.mobile = mobile
        # user.icon = icon  # 利用插件直接就可以保存
        #上传到七牛云
        save_path = upload_image(icon)
        user.yunicon = save_path
        user.save()
        return render(request, 'center.html', context={'user': user})


def login_qq(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    else:
        code_url = 'https://graph.qq.com/oauth2.0/authorize'
        parm = {
            'response_type': 'code',
            'client_id': '1110505456',
            'redirect_uri': 'www.ditanshouw.com/user/login/qq',
            'state':  'test'
        }
        auth_url = '%s?%s'%(code_url, urlencode(parm))
        return HttpResponseRedirect(auth_url)


#其中redirect_uri为回调url，qq服务器收到登录请求后调用你的后台实现
#www.323.com/qq  指向如下实现

#流程如下：
#1.www.323.com/login?type=qq
#2.--->跳转qq登录页面
#3.--->qq调用后台www.323.com/qq
#4.--->映射处理登录验证
#qq = QQ(^$#%%$)
#access_token = qq.get_access_token()
#openid = qq.get_openid(access_token)
#user_info = qq.get_userinfo(access_token,openid) #返回字典
#5.保持用户信息到本地数据库
#成功登录后跳转到登录前页面


#QQ登录
token_url = 'https://graph.qq.com/oauth2.0/token'
auth_url = 'https://graph.qq.com/oauth2.0/me'
class QQ(object):
    def __init__(self,appid,appkey,token_url,auth_url,user_info_url,redirect_uri,code,state):
        self.appid=appid
        self.appkey=appkey
        self.token_url=token_url
        self.auth_url=auth_url
        self.redirect_uri=redirect_uri
        self.code=code
        self.state=state
        self.user_info_url = user_info_url

    #获取access_token
    def get_access_token(self):
        parm = {
              'grant_type':'authorization_code',
                'client_id':self.appid,
                'client_secret':self.appkey,
                'redirect_uri':self.redirect_uri,
                'code':self.code
        }
        try:
            parm_token_url = '%s?%s'%(token_url, urlencode(parm))
            resp = urllib.request.urlopen(parm_token_url)
            content = resp.read()

            access_token = urllib.urlparse.parse_qs(content).get('access_token', [''])[0]
            return access_token

        except Exception as e:
            print(e.reason)

    #获取OpenID
    def get_openid(self,access_token):
        try:
            parm_auth_url = '%s?%s'%(self.auth_url, urlencode({'access_token': access_token,}))
            resp = urllib.request.urlopen(parm_auth_url)
            content = resp.read()
            content = content[content.find('(')+1:content.rfind(')')]
            data = json.loads(content)
            openid = data.get('openid')
            return openid

        except Exception as e:
            print(e)


    #获取uerinfo
    def get_userinfo(self,access_token,openid):
        parm = {
        'access_token':access_token,
        'oauth_consumer_key':self.appid,
        'openid':openid
         }
        try:
            parm_user_info_url = '%s?%s'%(self.user_info_url, urlencode(parm))
            resp = urllib.request.urlopen(parm_user_info_url)
            content = resp.read()
            user_info = json.loads(content)
            return user_info
        except Exception as e:
            print(e.reason)

