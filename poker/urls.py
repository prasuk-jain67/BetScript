from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import register
from django.contrib import admin


urlpatterns = [
    path('upload_bot/', views.upload_bot, name='upload_bot'),
    path('auth/register/', register, name='register'),
    path('',views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('replay/<int:match_id>/', views.replay, name='replay'),
    path('deploy_bot/', views.deploy_bot, name='deploy_bot'),
    path('contact_us/', views.contact_us, name='contact_us'),
    path('documentation/', views.documentation, name='documentation'),
    path('test_run/',views.test_run,name="test_run"),
    path('test_replay/<int:match_id>/', views.test_replay, name='test_replay'),
    path('test_match_results/<int:match_id>/', views.test_match_results, name='test_run_response2'),
    path('admin_panel/', views.admin_panel, name='admin_panel'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]