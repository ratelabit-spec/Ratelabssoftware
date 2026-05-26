import datetime

def update_or_insert_cost(supabase_client, user_id, property_id, tipo_coste, motivo, monto, fecha_inicio, base_calculo=None, canal=None, frecuencia='monthly'):
    """Gestiona la inserción y versionado (histórico) de costes de forma segura."""
    
    # 1. Calculamos las fechas
    fecha_fin_anterior = (fecha_inicio - datetime.timedelta(days=1)).isoformat()
    fecha_inicio_str = fecha_inicio.isoformat()

    try:
        if tipo_coste == "Fijo":
            tabla = "fixed_costs"
            
            # Buscamos si existe un coste vigente igual
            query = supabase_client.table(tabla).select("id").eq("property_id", property_id).eq("category", motivo).is_("valid_to", "null").execute()
            
            if query.data: 
                id_viejo = query.data[0]['id']
                supabase_client.table(tabla).update({"valid_to": fecha_fin_anterior}).eq("id", id_viejo).execute()
            
            # Insertamos el nuevo
            supabase_client.table(tabla).insert({
                "user_id": user_id, 
                "property_id": property_id, 
                "category": motivo, 
                "amount": monto, 
                "frequency": frecuencia,
                "valid_from": fecha_inicio_str
            }).execute()

        elif tipo_coste == "Variable":
            tabla = "variable_costs"
            
            # CORRECCIÓN DEL BUG NULL: Construimos la query paso a paso
            base_query = supabase_client.table(tabla).select("id").eq("property_id", property_id).eq("cost_type", motivo).is_("valid_to", "null")
            
            # Si hay canal buscamos coincidencia exacta, si no, buscamos los que sean NULL
            if canal and str(canal).strip() != "":
                query = base_query.eq("channel_name", str(canal).strip()).execute()
            else:
                query = base_query.is_("channel_name", "null").execute()
            
            if query.data:
                id_viejo = query.data[0]['id']
                supabase_client.table(tabla).update({"valid_to": fecha_fin_anterior}).eq("id", id_viejo).execute()
                
            # Limpiamos el canal para asegurarnos de que guardamos Null y no strings vacíos
            clean_canal = str(canal).strip() if canal and str(canal).strip() != "" else None

            supabase_client.table(tabla).insert({
                "user_id": user_id, 
                "property_id": property_id, 
                "cost_type": motivo, 
                "channel_name": clean_canal,
                "value": monto, 
                "basis": base_calculo,
                "valid_from": fecha_inicio_str
            }).execute()
            
        return True, "Coste guardado correctamente."

    except Exception as e:
        error_msg = f"Error en base de datos: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg