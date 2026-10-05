from django.contrib.auth.views import LogoutView
from django.urls import path

from . import confectioner, views

urlpatterns = [
    path("", views.menu_view, name="menu"),
    path("cart/coupon/", views.validate_coupon, name="validate_coupon"),
    path("cart/validate/", views.validate_order, name="validate_order"),
    path("cart/submit/", views.submit_order, name="submit_order"),
    path("cart/", views.cart_view, name="cart"),
    path("confeiteiro/entrar/", confectioner.ConfectionerLoginView.as_view(), name="confectioner_login"),
    path("confeiteiro/sair/", LogoutView.as_view(next_page="menu"), name="confectioner_logout"),
    path("confeiteiro/pedidos/", confectioner.orders, name="confectioner_orders"),
    path("confeiteiro/pedidos/<int:pk>/comprovante/", confectioner.download_receipt, name="confectioner_receipt"),
    path("confeiteiro/pedidos/<int:pk>/situacao/", confectioner.change_status, name="confectioner_status"),
]
