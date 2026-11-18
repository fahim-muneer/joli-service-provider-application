import { asset } from "../assets";
import { ANNOUNCEMENT } from "../config";
import Img from "./Img";
import { MegaphoneIcon } from "./Icons";

export default function AnnouncementBar() {
  return (
    <div className="announcement" role="region" aria-label="Announcements">
      <div className="page announcement__inner">
        <span className="announcement__badge">
          <Img src={asset("announcement")} fallback={<MegaphoneIcon />} />
        </span>
        {ANNOUNCEMENT && <span>{ANNOUNCEMENT}</span>}
      </div>
    </div>
  );
}
