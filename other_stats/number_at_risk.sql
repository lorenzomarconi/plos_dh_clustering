--------------
-- Nephropathy
--------------
WITH timepoints AS (
    SELECT 0 AS years
    UNION ALL SELECT 3
    UNION ALL SELECT 5
    UNION ALL SELECT 7
    UNION ALL SELECT 10
)
SELECT 
    cluster,
	t.years,
    COUNT(*) AS number_at_risk
FROM clustering.nephropathy n
JOIN clustering.clusters_cc c USING (idcentro, idana)
CROSS JOIN timepoints t
WHERE
	n.diagnosis = false
	OR EXTRACT (YEAR FROM n.onset_date) >= c.annoinizio + t.years
GROUP BY cluster, t.years
ORDER BY cluster, t.years
;

--------------
-- Retinopathy
--------------
WITH timepoints AS (
    SELECT 0 AS years
    UNION ALL SELECT 3
    UNION ALL SELECT 5
    UNION ALL SELECT 7
    UNION ALL SELECT 10
)
SELECT 
    cluster,
	t.years,
    COUNT(*) AS number_at_risk
FROM clustering.retinopathy r
JOIN clustering.clusters_cc c USING (idcentro, idana)
CROSS JOIN timepoints t
WHERE
	r.diagnosis = false
	OR EXTRACT (YEAR FROM r.onset_date) >= c.annoinizio + t.years
GROUP BY cluster, t.years
ORDER BY cluster, t.years
;

------------------------
-- Insulin prescription
------------------------
WITH timepoints AS (
    SELECT 0 AS years
    UNION ALL SELECT 3
    UNION ALL SELECT 5
    UNION ALL SELECT 7
    UNION ALL SELECT 10
),
first_insulin_prescription AS (
	SELECT
		idcentro, idana,
		MIN(data) AS onset_date
	FROM dati2.prescrizionidiabetefarmaci
	WHERE LEFT(codiceatc, 4) = 'A10A'
	GROUP BY idcentro, idana
)
SELECT 
    cluster,
	t.years,
    COUNT(*) AS number_at_risk
FROM clustering.clusters_cc c
LEFT JOIN first_insulin_prescription p USING (idcentro, idana)
CROSS JOIN timepoints t
WHERE
	p.onset_date IS NULL OR
	EXTRACT (YEAR FROM p.onset_date) >= c.annoinizio + t.years
GROUP BY cluster, t.years
ORDER BY cluster, t.years
;