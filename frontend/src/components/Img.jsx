/** An image from the Figma artwork, or `fallback` while the file has not been downloaded. */
export default function Img({ src, alt = "", fallback = null, ...props }) {
  if (!src) return fallback;
  return <img src={src} alt={alt} {...props} />;
}
