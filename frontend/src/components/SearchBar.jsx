import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { asset } from "../assets";
import Img from "./Img";
import { SearchIcon } from "./Icons";

export default function SearchBar({ onSearch }) {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  function submit(e) {
    e.preventDefault();
    const text = query.trim();
    navigate(text ? `/services?search=${encodeURIComponent(text)}` : "/services");
    onSearch?.();
  }

  return (
    <form className="search" role="search" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="site-search">Search services</label>
      <input id="site-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} />
      <button type="submit" aria-label="Search">
        <Img src={asset("search-icon")} fallback={<SearchIcon />} />
      </button>
    </form>
  );
}
