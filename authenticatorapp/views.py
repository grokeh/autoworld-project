from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import UserCreationForm

# ✅ Your first login view — fixed
def login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)  # avoid calling the function 'login' here
            return redirect('home')
        else:
            return render(request, 'authenticatorapp/login.html', {'error': 'Invalid credentials'})
    return render(request, 'authenticatorapp/login.html')


# ✅ Your second login_view — still works with ecommerce template if needed
def login_view(request):
    template = 'ecommerceapp/login.html'
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)  # same fix here
            return redirect('home')
        else:
            return render(request, template, {'error': 'Invalid credentials'})
    return render(request, template)


# ✅ Added Register view
def Register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)  # log in user after registering
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'authenticatorapp/register.html', {'form': form})


# ✅ Added Logout view
def Logout(request):
    auth_logout(request)
    return render(request, 'authenticatorapp/logout.html')


