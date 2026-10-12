import { useParams } from 'react-router-dom';
import { TextField } from '../components/TextField';
import { SelectField } from '../components/SelectField';
import { post } from '../api/client';

const STATUSES = ['Planned', 'Active', 'Paused', 'Done'];

export default function ProjectEdit() {
  const { projectId } = useParams();
  return (
    <form onSubmit={(event) => { event.preventDefault(); post(`/projects/${projectId}`, new FormData(event.currentTarget)); }}>
      <h1>Edit project</h1>
      <TextField name="project_name" label="Project name" required maxLength={100} />
      <SelectField name="status" label="Status" options={STATUSES} required />
      <TextField name="due_date" label="Due date" type="date" />
      <button type="submit">Save changes</button>
    </form>
  );
}
