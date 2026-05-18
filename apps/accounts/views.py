from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, View

User = get_user_model()


class RegisterView(FormView):
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:activation_sent")

    def get_form_class(self):
        from apps.accounts.forms import RegistrationForm

        return RegistrationForm

    def form_valid(self, form):
        from apps.accounts.emails import send_activation_email

        user = form.save(commit=False)
        user.is_active = False
        user.save()
        send_activation_email(user, self.request)
        return super().form_valid(form)


class ActivationSentView(TemplateView):
    template_name = "accounts/activation_sent.html"


class ActivationInvalidView(TemplateView):
    template_name = "accounts/activation_invalid.html"


class ActivateView(View):
    def get(self, request, uidb64: str, token: str):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return redirect("accounts:activation_invalid")

        if user.is_active:
            messages.info(
                request,
                _("Konto jest już aktywne. Możesz się zalogować."),
            )
            return redirect("accounts:login")

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            messages.success(request, _("Konto aktywowane. Zaloguj się."))
            return redirect("accounts:login")

        return redirect("accounts:activation_invalid")


class ResendActivationView(FormView):
    template_name = "accounts/resend.html"
    success_url = reverse_lazy("accounts:activation_resend")

    def get_form_class(self):
        from apps.accounts.forms import ResendActivationForm

        return ResendActivationForm

    def form_valid(self, form):
        from apps.accounts.emails import send_activation_email

        email = form.cleaned_data["email"]
        try:
            user = User.objects.get(email__iexact=email, is_active=False)
        except User.DoesNotExist:
            user = None
        if user is not None:
            send_activation_email(user, self.request)
        return render(self.request, "accounts/resend_done.html")
