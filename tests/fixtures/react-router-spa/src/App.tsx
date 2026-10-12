import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Signup from './pages/Signup';
import ProfileSettings from './pages/ProfileSettings';
import ProjectEdit from './pages/ProjectEdit';
import About from './pages/About';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/signup" element={<Signup />} />
        <Route path="/settings/profile" element={<ProfileSettings />} />
        <Route path="/projects/:projectId/edit" element={<ProjectEdit />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </BrowserRouter>
  );
}
