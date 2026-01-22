import { redirect } from "next/navigation";

export default function Home() {
  // Redirect to library page
  redirect("/library");
}
