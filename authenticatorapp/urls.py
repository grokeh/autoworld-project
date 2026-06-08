from . import views
from django.urls import path

urlpatterns = [
    path('login/', views.login,name='login'),
     path('logout/', views.Logout, name='logout'),        
    path('register/', views.Register, name='register'),  
]