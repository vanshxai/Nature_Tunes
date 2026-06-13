import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { DndProvider } from 'react-dnd'
import { HTML5Backend } from 'react-dnd-html5-backend'
import Root from './Root.jsx'
import './styles/global.css'
import './styles/timeline.css'
import './styles/library.css'
import './styles/admin.css'
import './styles/nav.css'
import './styles/dashboard.css'

// Note: intentionally not wrapped in StrictMode — its double-invoke of effects
// in dev causes Tone.js players to initialise twice.
createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <DndProvider backend={HTML5Backend}>
      <Root />
    </DndProvider>
  </BrowserRouter>,
)
