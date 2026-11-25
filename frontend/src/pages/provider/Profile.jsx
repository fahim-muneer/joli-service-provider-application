
import { useState } from "react";
import { getMe, updateMe } from "../../api/provider";
import Button from "../../components/Button";
import AccountCard from "../../components/portal/AccountCard";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";

function getProfileForm(profile) {
  return {
    business_name: profile?.business_name ?? "",
    bio: profile?.bio ?? "",
    experience_years: profile?.experience_years ?? "",
    languages: (profile?.languages ?? []).join(", "),
  };
}

export default function Profile() {
  const me = useLoad(getMe);

  const [formOverride, setFormOverride] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  // Use API data initially; use edited values after the user makes changes.
  const form = formOverride ?? getProfileForm(me.data);

  if (me.status === "loading") {
    return <Spinner />;
  }

  if (me.status === "error") {
    return (
      <section className="panel">
        <ErrorMessage message={me.error} onRetry={me.reload} />
      </section>
    );
  }

  const update = (field) => (e) => {
    setSaved(false);

    setFormOverride((current) => ({
      ...(current ?? getProfileForm(me.data)),
      [field]: e.target.value,
    }));
  };

  async function handleSubmit(e) {
    e.preventDefault();

    setError("");
    setBusy(true);

    try {
      const body = {
        business_name: form.business_name,
        bio: form.bio,
        languages: form.languages
          .split(",")
          .map((language) => language.trim())
          .filter(Boolean),
      };

      if (form.experience_years !== "") {
        body.experience_years = Number(form.experience_years);
      }

      const updatedProfile = await updateMe(body);

      me.setData(updatedProfile);
      setFormOverride(getProfileForm(updatedProfile));
      setSaved(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AccountCard>
      <p className="muted">
        {me.data.full_name} · {me.data.phone} · {me.data.email}
      </p>

      <form className="form" onSubmit={handleSubmit}>
        <label>
          Business name
          <input
            value={form.business_name}
            onChange={update("business_name")}
            maxLength={150}
          />
        </label>

        <label>
          About you
          <textarea
            rows={4}
            value={form.bio}
            onChange={update("bio")}
          />
        </label>

        <label>
          Years of experience
          <input
            type="number"
            min="0"
            max="80"
            value={form.experience_years}
            onChange={update("experience_years")}
          />
        </label>

        <label>
          Languages (comma separated)
          <input
            value={form.languages}
            onChange={update("languages")}
            placeholder="English, Hindi, Kannada"
          />
        </label>

        {saved && (
          <p className="notice" role="status">
            Saved.
          </p>
        )}

        <ErrorMessage message={error} />

        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
      </form>
    </AccountCard>
  );
}
