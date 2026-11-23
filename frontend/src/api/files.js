import { api } from "./client";

/** Private files (ID proofs) need the login token, so a plain link would be refused.
 *  We download the file with the token and show it in a new tab. */
export async function openProtectedFile(url) {
  const tab = window.open("", "_blank"); // opened first so the browser does not block the popup
  try {
    const { data } = await api.get(url, { responseType: "blob" });
    const objectUrl = URL.createObjectURL(data);
    if (tab) {
      tab.location.href = objectUrl;
    } else {
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "document";
      link.click();
    }
  } catch (error) {
    tab?.close();
    throw error;
  }
}
