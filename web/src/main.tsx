import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Footer, Header, Hero } from './PageChrome';

const header = document.getElementById('header-root');
const hero = document.getElementById('hero-root');
const footer = document.getElementById('footer-root');

if (!header || !hero || !footer) {
  throw new Error('The page is missing a React mounting point.');
}

createRoot(header).render(
  <StrictMode>
    <Header />
  </StrictMode>,
);

createRoot(hero).render(
  <StrictMode>
    <Hero />
  </StrictMode>,
);

createRoot(footer).render(
  <StrictMode>
    <Footer />
  </StrictMode>,
);