const btnMobile = document.querySelector('.btnMobile')
const navMobile = document.querySelector('.itemsMobile')

const toggleBtn = () => {
    if (navMobile.style.transform === 'translateX(0%)')
        navMobile.style.transform = 'translateX(100%)'
    else
        navMobile.style.transform = 'translateX(0%)'
}

btnMobile.addEventListener('click', toggleBtn)