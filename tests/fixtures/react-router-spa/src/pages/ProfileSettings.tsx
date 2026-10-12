import { TextField } from '../components/TextField';
import { post } from '../api/client';

export default function ProfileSettings() {
  return (
    <form onSubmit={(event) => { event.preventDefault(); post('/profile', new FormData(event.currentTarget)); }}>
      <h1>Profile</h1>
      <TextField name="display_name" label="Display name" required maxLength={40} />
      <TextField name="job_title" label="Job title" maxLength={60} />
      <label htmlFor="bio">About you</label>
      <textarea id="bio" name="bio" maxLength={280} />
      <fieldset>
        <legend>Theme</legend>
        <label><input type="radio" name="theme" value="light" /> Light</label>
        <label><input type="radio" name="theme" value="dark" /> Dark</label>
        <label><input type="radio" name="theme" value="system" /> System</label>
      </fieldset>
      <button type="submit">Save profile</button>
      <p role="status" hidden>Profile saved</p>
    </form>
  );
}
