


// ЛЕНИВАЯ ЗАГРУЗКА НАЧАЛО

const lazyImages = document.querySelectorAll('.lazy-images');
// const windowHeight = document.documentElement.clientHeight;

let lazyImagesPositions = [];


if (lazyImages.length > 0) {
   lazyImages.forEach(img => {
      if (img.dataset.src || img.dataset.srcset) {
         lazyImagesPositions.push(img.getBoundingClientRect().top + pageYOffset);
         lazyScrollCheck();
      }
   });
}

window.addEventListener("scroll", lazyScroll);

function lazyScroll() {
   if (document.querySelectorAll('.lazy-images').length > 0) {
      lazyScrollCheck();
   }
}

function lazyScrollCheck() {
   let imgIndex = lazyImagesPositions.findIndex(item => pageYOffset > item - screnHight);
   if (imgIndex >= 0) {
      if (lazyImages[imgIndex].dataset.src) {
         lazyImages[imgIndex].src = lazyImages[imgIndex].dataset.src;
         lazyImages[imgIndex].removeAttribute('data-src');
         lazyImages[imgIndex].classList.remove('lazy-images');
      } else if (lazyImages[imgIndex].dataset.srcset) {
         lazyImages[imgIndex].srcser = lazyImages[imgIndex].dataset.srcset;
         lazyImages[imgIndex].removeAttribute('data-srcset');
         lazyImages[imgIndex].classList.remove('lazy-images');
      }
      delete lazyImagesPositions[imgIndex];
   }
}

// ЛЕНИВАЯ ЗАГРУЗКА КОНЕЦ