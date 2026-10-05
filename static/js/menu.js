document.addEventListener('DOMContentLoaded', function () {
    const menu = document.querySelector('#showMenu')
    const promotions = document.querySelector('#showPromotions')
    const buttons = document.querySelectorAll('.linkMenu')

    const cards = menu ? Array.from(menu.querySelectorAll('.card[data-category]')) : []

    function filterProducts(category) {
        if (!menu) return
        cards.forEach(card => {
            if (category === 'all' || card.dataset.category === category) {
                card.style.display = ''
            } else {
                card.style.display = 'none'
            }
        })

        buttons.forEach(btn => {
            if (btn.dataset.filter === category) {
                btn.classList.add('active')
            } else {
                btn.classList.remove('active')
            }
        })

        const visible = cards.some(c => c.style.display !== 'none')
        if (!visible) {
            menu.innerHTML = '<p class="empty">Nenhum docinho encontrado por aqui!</p>'
        } else if (!menu.querySelector('.card')) {
            // should not happen
        }
    }

    buttons.forEach(btn => {
        btn.addEventListener('click', () => filterProducts(btn.dataset.filter))
    })
})
