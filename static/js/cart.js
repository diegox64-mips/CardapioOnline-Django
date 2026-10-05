document.addEventListener('DOMContentLoaded', function () {
    const productsData = document.getElementById('products-data')
    const products = productsData ? JSON.parse(productsData.textContent) : []

    function getCart() {
        try {
            const stored = JSON.parse(localStorage.getItem('cart'))
            return Array.isArray(stored) ? stored.filter(item => item && Number.isInteger(item.id)) : []
        } catch {
            return []
        }
    }

    function setCart(cart) {
        localStorage.setItem('cart', JSON.stringify(cart))
    }

    function productById(id) {
        return products.find(p => p.id === id)
    }

    function formatPrice(value) {
        return value.toFixed(2).replace('.', ',')
    }

    function showToast(message) {
        if (typeof Toastify !== 'function') return
        Toastify({
            text: message,
            duration: 5000,
            newWindow: true,
            close: true,
            gravity: "bottom",
            position: "right",
            stopOnFocus: true,
            style: {
                background: "#F6BBB0",
                color: "#602E16",
                fontWeight: "700",
                border: "2px solid #602E16",
                borderRadius: "18px",
                boxShadow: "0 10px 30px 0 rgba(96, 46, 22, 0.25)"
            }
        }).showToast()
    }

    function addToCart(id) {
        const cart = getCart()
        const existing = cart.find(item => item.id === id)
        if (existing) {
            existing.qtd += 1
        } else {
            cart.push({ id: id, qtd: 1 })
        }
        setCart(cart)
        showToast('Produto adicionado no carrinho de compras.')
        updateCartNotify()
    }

    function updateCartNotify() {
        const cartNotify = document.querySelector('.cartNotify')
        if (!cartNotify) return
        cartNotify.style.display = getCart().length > 0 ? 'block' : 'none'
    }

    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', function () {
            const id = parseInt(this.dataset.id, 10)
            if (!Number.isNaN(id)) addToCart(id)
        })
    })

    updateCartNotify()

    // Shopping cart page logic
    const showItems = document.querySelector('#showItems')
    if (!showItems) return

    const showAllItemsValue = document.querySelector('#showAllItemsValue')
    const showDelivery = document.querySelector('#showDelivery')
    const showDiscount = document.querySelector('#showDiscount')
    const showTotal = document.querySelector('#showTotal')
    const inputPromotionCode = document.querySelector('#promotionCode')
    const btnAddPromotionCode = document.querySelector('#addPromotionCode')
    const couponMessage = document.querySelector('#couponMessage')
    const btnWantDelivery = document.querySelector('#wantDelivery')
    const btnDontWantDelivery = document.querySelector('#dontWantDelivery')
    const btnGenerateOrder = document.querySelector('#generateOrder')
    const customerForm = document.querySelector('#customerDetails')
    const deliveryAddress = document.querySelector('#deliveryAddress')
    const cartStep = document.querySelector('#cartStep')
    const paymentStep = document.querySelector('#paymentStep')
    const paymentStepTitle = document.querySelector('#paymentStepTitle')
    const paymentTotal = document.querySelector('#paymentTotal')
    const receiptUploadSection = document.querySelector('#receiptUploadSection')
    const receiptFile = document.querySelector('#receiptFile')
    const btnSubmitOrder = document.querySelector('#submitOrder')
    const paymentMessage = document.querySelector('#paymentMessage')
    const orderComplete = document.querySelector('#orderComplete')
    const orderReference = document.querySelector('#orderReference')
    const orderCompleteMessage = document.querySelector('#orderCompleteMessage')
    const btnBackToCart = document.querySelector('#backToCart')

    const settings = JSON.parse(document.getElementById('checkout-settings').textContent)
    const deliveryFee = Number(settings.delivery_fee)
    const minimumOrder = Number(settings.minimum_order)
    const minimumMessage = document.getElementById('minimumOrderMessage')
    let wantsDelivery = false
    let submitting = false
    let quoteToken = ''
    let requestToken = ''
    let couponCode = ''
    let deliveryValue = 0
    let discountValue = 0

    function sanitizeQuantity(qtd) {
        const n = parseInt(qtd, 10)
        return Number.isNaN(n) || n < 1 ? 1 : n > 99 ? 99 : n
    }

    function generateCart() {
        const cartItems = getCart()
        const cart = []
        let allItemsValue = 0

        cartItems.forEach(prod => {
            const item = productById(prod.id)
            if (!item) return
            item.qtd = sanitizeQuantity(prod.qtd)
            allItemsValue += Math.round(item.price * 100) * item.qtd
            cart.push(item)
        })

        return { cart, allItemsValue: allItemsValue / 100 }
    }

    function addItem(id) {
        const cart = getCart()
        const item = cart.find(i => i.id === id)
        if (item && item.qtd < 99) item.qtd += 1
        setCart(cart)
        init()
    }

    function remItem(id) {
        const cart = getCart()
        const idx = cart.findIndex(i => i.id === id)
        if (idx === -1) return
        if (cart[idx].qtd > 1) {
            cart[idx].qtd -= 1
        } else {
            cart.splice(idx, 1)
            showToast('Produto removido do carrinho de compras.')
        }
        setCart(cart)
        init()
    }

    function buildItem(prod) {
        const price = formatPrice(prod.price * prod.qtd)
        return `
        <div class="item">
            <img src="${prod.img || '/static/img/product-placeholder.svg'}" alt="Imagem de um(a) ${prod.name}">
            <div>
                <p class="title">${prod.name}</p>
                <p>${prod.description}</p>
                <div class="bottom">
                    <div class="counter">
                        <button type="button" class="rem-item" data-id="${prod.id}">-</button>
                        <input type="text" value="${prod.qtd}" disabled>
                        <button type="button" class="add-item" data-id="${prod.id}">+</button>
                    </div>
                    <p class="price">R$ <span>${price}</span></p>
                </div>
            </div>
        </div>
        <hr>`
    }

    function init() {
        const { cart, allItemsValue } = generateCart()
        cart.sort((a, b) => a.type - b.type)

        let html = ''
        if (cart.length > 0) {
            cart.forEach(data => { html += buildItem(data) })
        } else {
            html = '<p>Sua sacolinha ainda está vazia. Que tal escolher um docinho?</p>'
        }
        showItems.innerHTML = html

        showItems.querySelectorAll('.add-item').forEach(btn => {
            btn.addEventListener('click', () => addItem(parseInt(btn.dataset.id, 10)))
        })
        showItems.querySelectorAll('.rem-item').forEach(btn => {
            btn.addEventListener('click', () => remItem(parseInt(btn.dataset.id, 10)))
        })

        const totalValue = allItemsValue + deliveryValue
        const discount = Math.round(Math.round(allItemsValue * 100) * discountValue / 100) / 100
        const missing = Math.max(0, Math.round(minimumOrder * 100) - Math.round(allItemsValue * 100) + Math.round(discount * 100)) / 100
        btnGenerateOrder.disabled = submitting || cart.length === 0 || missing > 0
        minimumMessage.textContent = missing > 0
            ? `Pedido mínimo: R$ ${formatPrice(minimumOrder)} em produtos após descontos, sem entrega. Faltam R$ ${formatPrice(missing)}.`
            : minimumOrder > 0 ? `Pedido mínimo de R$ ${formatPrice(minimumOrder)} atingido.` : ''
        showAllItemsValue.textContent = 'R$ ' + formatPrice(allItemsValue)
        showDelivery.textContent = '+ R$ ' + formatPrice(deliveryValue)
        showDiscount.textContent = '- R$ ' + formatPrice(discount)
        showTotal.textContent = 'R$ ' + formatPrice(totalValue - discount)
    }

    function chooseDelivery(option) {
        wantsDelivery = option
        deliveryAddress.hidden = !option
        deliveryAddress.disabled = !option
        deliveryAddress.querySelectorAll('input, select').forEach(field => {
            field.required = option && field.name !== 'complement'
        })
        if (option) {
            btnWantDelivery.classList.add('active')
            btnDontWantDelivery.classList.remove('active')
            deliveryValue = deliveryFee
        } else {
            btnWantDelivery.classList.remove('active')
            btnDontWantDelivery.classList.add('active')
            deliveryValue = 0
        }
        init()
    }

    async function addDiscount() {
        const code = (inputPromotionCode.value || '').trim()
        if (!code) {
            couponCode = ''
            discountValue = 0
            couponMessage.textContent = 'Cupom removido.'
            init()
            return
        }

        couponCode = ''
        discountValue = 0
        init()
        btnAddPromotionCode.disabled = true
        try {
            const response = await fetch(btnAddPromotionCode.dataset.validationUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                },
                body: JSON.stringify({code}),
            })
            const result = await response.json()
            if (!response.ok) {
                couponMessage.textContent = result.error || 'Cupom não encontrado.'
                showToast(couponMessage.textContent)
                return
            }
            couponCode = result.code
            discountValue = Number(result.discount_percent)
            couponMessage.textContent = `Cupom ${couponCode} aplicado: ${formatPrice(discountValue)}% de desconto nos produtos.`
            showToast('Cupom aplicado com sucesso!')
            init()
        } catch {
            couponMessage.textContent = 'Não foi possível validar o cupom. Tente novamente.'
            showToast(couponMessage.textContent)
        } finally {
            btnAddPromotionCode.disabled = false
        }
    }

    async function generateQuote() {
        if (submitting || btnGenerateOrder.disabled || !customerForm.reportValidity()) return
        const { cart } = generateCart()
        const payload = {
            items: cart.map(item => ({id: item.id, qtd: item.qtd})),
            delivery: wantsDelivery,
            coupon: couponCode,
            customer: Object.fromEntries(new FormData(customerForm)),
        }
        submitting = true
        init()
        let error = ''
        try {
            const response = await fetch(btnGenerateOrder.dataset.validationUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                },
                body: JSON.stringify(payload),
            })
            const result = await response.json()
            if (!response.ok) {
                error = result.error || 'Não foi possível validar o pedido.'
            } else {
                quoteToken = result.quote_token
                requestToken = crypto.randomUUID()
                showAllItemsValue.textContent = 'R$ ' + formatPrice(Number(result.subtotal))
                showDiscount.textContent = '- R$ ' + formatPrice(Number(result.discount))
                showDelivery.textContent = '+ R$ ' + formatPrice(Number(result.delivery_fee))
                showTotal.textContent = 'R$ ' + formatPrice(Number(result.total))
                paymentTotal.textContent = 'R$ ' + formatPrice(Number(result.total))
                paymentMessage.textContent = ''
                btnSubmitOrder.disabled = false
                updateProofMethod()
                cartStep.hidden = true
                paymentStep.hidden = false
                paymentStepTitle.focus()
            }
        } catch {
            error = 'Não foi possível validar o pedido. Tente novamente.'
        } finally {
            submitting = false
            if (!cartStep.hidden) init()
            if (error) {
                minimumMessage.textContent = error
                showToast(error)
            }
        }
    }

    function updateProofMethod() {
        const selected = document.querySelector('input[name="proofMethod"]:checked')
        const method = selected ? selected.value : 'upload'
        receiptUploadSection.hidden = method !== 'upload'
        receiptFile.required = method === 'upload'
        btnSubmitOrder.textContent = method === 'upload'
            ? 'Enviar pedido e comprovante'
            : 'Salvar pedido e abrir WhatsApp'
    }

    async function submitOrder() {
        if (submitting || !quoteToken || !requestToken) return
        const selected = document.querySelector('input[name="proofMethod"]:checked')
        const method = selected ? selected.value : 'upload'
        if (method === 'upload' && !receiptFile.files.length) {
            receiptFile.reportValidity()
            return
        }

        const { cart } = generateCart()
        const payload = {
            request_token: requestToken,
            quote_token: quoteToken,
            items: cart.map(item => ({id: item.id, qtd: item.qtd})),
            delivery: wantsDelivery,
            coupon: couponCode,
            customer: Object.fromEntries(new FormData(customerForm)),
            proof_method: method,
        }
        const body = new FormData()
        body.append('payload', JSON.stringify(payload))
        if (method === 'upload') body.append('receipt', receiptFile.files[0])

        submitting = true
        btnSubmitOrder.disabled = true
        paymentMessage.textContent = ''
        try {
            const response = await fetch(btnSubmitOrder.dataset.submitUrl, {
                method: 'POST',
                headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value},
                body,
            })
            const result = await response.json()
            if (!response.ok) {
                paymentMessage.textContent = result.error || 'Não foi possível registrar o pedido.'
                return
            }
            setCart([])
            updateCartNotify()
            if (method === 'whatsapp') {
                window.location.assign(result.whatsapp_url)
                return
            }
            orderReference.textContent = result.order_reference
            orderCompleteMessage.textContent = result.message
            paymentStep.hidden = true
            orderComplete.hidden = false
            orderComplete.querySelector('h2').focus()
        } catch {
            paymentMessage.textContent = 'Não foi possível enviar o pedido. Tente novamente.'
        } finally {
            submitting = false
            if (paymentStep.hidden === false) btnSubmitOrder.disabled = false
        }
    }

    if (btnAddPromotionCode) btnAddPromotionCode.addEventListener('click', addDiscount)
    if (btnWantDelivery) btnWantDelivery.addEventListener('click', () => chooseDelivery(true))
    if (btnDontWantDelivery) btnDontWantDelivery.addEventListener('click', () => chooseDelivery(false))
    if (btnGenerateOrder) btnGenerateOrder.addEventListener('click', generateQuote)
    if (btnBackToCart) btnBackToCart.addEventListener('click', () => {
        quoteToken = ''
        requestToken = ''
        receiptFile.value = ''
        btnSubmitOrder.disabled = true
        paymentStep.hidden = true
        cartStep.hidden = false
    })
    document.querySelectorAll('input[name="proofMethod"]').forEach(input => input.addEventListener('change', updateProofMethod))
    if (btnSubmitOrder) btnSubmitOrder.addEventListener('click', submitOrder)


    init()
})
