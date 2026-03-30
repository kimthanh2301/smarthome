from django.urls import path
from customers import views

urlpatterns = [
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/regenerate-api-key/', views.regenerate_api_key, name='regenerate_api_key'),
]
