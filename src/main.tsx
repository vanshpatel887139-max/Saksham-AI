import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// The static boot splash in index.html covers the bundle fetch and evaluation
// window. It has to come down *before* React paints, otherwise the app renders
// behind a fully-opaque overlay and the user watches nothing happen for a
// frame. Removing the node is also cheaper than hiding it, which would leave an
// empty full-screen layer swallowing the first click.
document.getElementById('boot')?.remove()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
