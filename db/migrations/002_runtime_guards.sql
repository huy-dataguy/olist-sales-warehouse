-- Reviewed operational guards. All mutations are scoped to one run and lease.
CREATE FUNCTION ops.assert_lease(p_run uuid, p_fence bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ops AS $fn$
DECLARE l ops.pipeline_leases;
BEGIN
 SELECT * INTO l FROM ops.pipeline_leases WHERE lease_name='warehouse' FOR UPDATE;
 IF NOT FOUND OR l.owner_run_id<>p_run OR l.fencing_token<>p_fence OR l.expires_at<=clock_timestamp() THEN
   RAISE EXCEPTION 'Lease expired or stale owner/fence';
 END IF;
 RETURN true;
END $fn$;

CREATE FUNCTION ops.checkpoint(p_model text, p_cut bigint, p_run uuid, p_fence bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ops AS $fn$
BEGIN
 PERFORM ops.assert_lease(p_run,p_fence);
 INSERT INTO ops.model_checkpoints(model_name,source_cut,successful_run_id,model_version)
 VALUES(p_model,p_cut,p_run,'2.0.0') ON CONFLICT(model_name) DO UPDATE
 SET source_cut=excluded.source_cut, successful_run_id=excluded.successful_run_id, model_version=excluded.model_version, updated_at=clock_timestamp();
 RETURN true;
END $fn$;
