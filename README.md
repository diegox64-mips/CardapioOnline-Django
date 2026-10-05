# Doces da Malu
### Cardápio digital demonstrativo em Django

Uma aplicação de portfólio para demonstrar catálogo de produtos, carrinho e fluxo de pedidos com Django.

> **Demonstração:** produtos, preços e imagens são fictícios. O pagamento é apenas ilustrativo. Não use dados reais de clientes, contatos ou pagamentos.

## Funcionalidades

- Catálogo com filtros por categoria
- Carrinho com cálculo de valores e cupons
- Fluxo de pedido com opção de comprovante
- Painel administrativo para produtos e pedidos
- Configurações de entrega e horário de atendimento
- Ambiente local com Docker Compose

## Tecnologias

Python · Django · SQLite · HTML · CSS · JavaScript · Docker

## Como executar

1. Copie `.env.example` para `.env`.
2. No `.env`, substitua `SECRET_KEY` e `ADMIN_URL_PREFIX` por valores aleatórios próprios.
3. Inicie a aplicação:

   ```bash
   docker compose up --build
   ```

4. Acesse `http://localhost:8000/`.

Para criar um usuário administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

Para carregar os produtos fictícios no banco vazio:

```bash
docker compose exec web python manage.py loaddata fixtures/products.json
```

## Testes

```bash
docker compose exec web python manage.py test
```

## Observação

Este projeto é uma demonstração de portfólio. Configure e revise todos os dados antes de qualquer uso real.
