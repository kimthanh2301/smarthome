from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from customers.forms import ProfileForm, form_validation_error
from customers.models import Profile
from devices.models import Device


@method_decorator(login_required(login_url='login'), name='dispatch')
class ProfileView(View):
    profile = None

    def dispatch(self, request, *args, **kwargs):
        self.profile, __ = Profile.objects.get_or_create(user=request.user)
        return super(ProfileView, self).dispatch(request, *args, **kwargs)

    def get(self, request):
        # Thống kê thiết bị
        total_devices = Device.objects.filter(user=request.user).count()
        online_devices = Device.objects.filter(user=request.user, is_online=True).count()
        
        context = {
            'profile': self.profile,
            'segment': 'profile',
            'total_devices': total_devices,
            'online_devices': online_devices,
        }
        return render(request, 'customers/profile.html', context)

    def post(self, request):
        form = ProfileForm(request.POST, request.FILES, instance=self.profile)

        if form.is_valid():
            profile = form.save()
            profile.user.first_name = form.cleaned_data.get('first_name')
            profile.user.last_name = form.cleaned_data.get('last_name')
            profile.user.email = form.cleaned_data.get('email')
            profile.user.save()

            messages.success(request, 'Profile saved successfully')
        else:
            messages.error(request, form_validation_error(form))
        return redirect('profile')


@login_required(login_url='login')
@require_POST
def regenerate_api_key(request):
    """Tạo lại API key mới"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    new_key = profile.generate_api_key()
    messages.success(request, 'Đã tạo API Key mới thành công!')
    return redirect('profile')
