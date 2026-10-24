import { redirect } from 'next/navigation';

export default async function Page() {
  // The root URL is the application entry point, not the public property feed.
  // Send signed-out visitors to the supported sign-in page; its callback flow
  // returns authenticated users to the dashboard.
  redirect('/auth/sign-in');
}
