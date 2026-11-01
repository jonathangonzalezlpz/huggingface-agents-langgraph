import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { chooseMode, createServices, StudioApp } from './app/bootstrap';
import './styles/index.css';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

const mode = chooseMode(window.location.search, import.meta.env.VITE_STUDIO_MODE);

createRoot(root).render(
  <StrictMode>
    <StudioApp services={createServices(mode)} />
  </StrictMode>,
);
