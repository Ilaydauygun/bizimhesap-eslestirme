import { useEffect, useState, useCallback } from "react";
export default function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    fn().then(setData).catch((e) => setError(e.userMessage || "Hata")).finally(() => setLoading(false));
  }, deps); // eslint-disable-line
  useEffect(reload, [reload]);
  return { data, error, loading, reload };
}
