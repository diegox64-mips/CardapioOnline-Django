from functools import wraps
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import ConfectionerLoginForm
from .models import Order


class ConfectionerLoginView(LoginView):
    template_name = "confectioner/login.html"
    authentication_form = ConfectionerLoginForm
    success_url = reverse_lazy("confectioner_orders")

    def get_success_url(self):
        return self.get_redirect_url() or str(self.success_url)


def confectioner_required(view):
    @wraps(view)
    def checked(request, *args, **kwargs):
        if not request.user.is_active or not (request.user.is_superuser or request.user.groups.filter(name="Confeiteiro").exists()):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return never_cache(login_required(checked, login_url="confectioner_login"))


@confectioner_required
def orders(request):
    selected_date = request.GET.get("date", "")
    queryset = Order.objects.all()
    if selected_date:
        day = parse_date(selected_date)
        if day is None:
            return HttpResponseBadRequest("Informe uma data válida.")
        queryset = queryset.filter(created_at__date=day)
    page = Paginator(queryset, 30).get_page(request.GET.get("page"))
    return render(request, "confectioner/orders.html", {
        "page_obj": page,
        "selected_date": selected_date,
        "status_choices": Order.Status.choices,
    })


@confectioner_required
@require_POST
def change_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    status = request.POST.get("status")
    if status not in Order.Status.values:
        return HttpResponseBadRequest("Situação inválida.")
    order.status = status
    order.save(update_fields=["status", "updated_at"])
    return redirect("confectioner_orders")


@confectioner_required
def download_receipt(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not order.receipt:
        raise Http404
    try:
        receipt = order.receipt.open("rb")
    except OSError as error:
        raise Http404 from error
    extension = Path(order.receipt.name).suffix.lower()
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
    response = FileResponse(
        receipt,
        as_attachment=True,
        filename=f"{order.reference}-comprovante{extension}",
        content_type=content_types.get(extension, "application/octet-stream"),
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
