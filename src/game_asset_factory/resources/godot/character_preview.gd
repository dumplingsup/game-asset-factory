extends SceneTree
## Actual AnimationPlayer/Skeleton3D playback, including donor-library reuse.

var model_path := ""
var donor_path := ""
var output := ""
var material_mode := "source"
var actor: Node3D
var donor: Node3D
var actor_player: AnimationPlayer
var donor_player: AnimationPlayer
var world: Node3D
var bounds := AABB()
var shots: Array[Dictionary] = []
var checks: Array[Dictionary] = []
var segments: Array[Dictionary] = []
var motion_libraries: Array[String] = []
var preview_config: Dictionary = {}
var morph_checks: Array[Dictionary] = []
var has_failed := false
var interactive_exit := false
var selected_outfit := 0

func _initialize() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--model="): model_path = argument.trim_prefix("--model=")
		if argument.begins_with("--donor="): donor_path = argument.trim_prefix("--donor=")
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		if argument.begins_with("--material-mode="): material_mode = argument.trim_prefix("--material-mode=")
		if argument.begins_with("--preview-config="):
			preview_config = JSON.parse_string(FileAccess.get_file_as_string(argument.trim_prefix("--preview-config=")))
	_run.call_deferred()

func fail(message: String) -> void:
	has_failed = true
	push_error(message)
	quit(2)

func load_actor(path: String) -> Node3D:
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_file(path, state) != OK:
		return null
	return document.generate_scene(state) as Node3D

func player_for(node: Node3D) -> AnimationPlayer:
	for child: Node in node.find_children("*", "AnimationPlayer", true, false):
		return child as AnimationPlayer
	return null

func skeleton_pose(node: Node3D) -> Dictionary:
	var result := {}
	for child: Node in node.find_children("*", "Skeleton3D", true, false):
		var skeleton := child as Skeleton3D
		for index: int in skeleton.get_bone_count():
			var rotation := skeleton.get_bone_pose_rotation(index)
			var position := skeleton.get_bone_pose_position(index)
			result[skeleton.get_bone_name(index)] = [rotation.x,rotation.y,rotation.z,rotation.w,position.x,position.y,position.z]
	return result

func pose_distance(a: Dictionary, b: Dictionary) -> float:
	var distance := 0.0
	if a.size() != b.size(): return INF
	for key: String in a:
		if not b.has(key): return INF
		var first: Array = a[key]
		var second: Array = b[key]
		var qa := Quaternion(first[0],first[1],first[2],first[3]).normalized()
		var qb := Quaternion(second[0],second[1],second[2],second[3]).normalized()
		distance = maxf(distance, qa.angle_to(qb))
	return distance

func baked_vertices(node: Node3D) -> PackedVector3Array:
	var result := PackedVector3Array()
	for child: Node in node.find_children("*", "MeshInstance3D", true, false):
		var instance := child as MeshInstance3D
		if instance.skin == null: continue
		var mesh := instance.bake_mesh_from_current_skeleton_pose()
		if mesh == null: continue
		for surface: int in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(surface)
			var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for point: Vector3 in positions:
				result.append(instance.global_transform * point)
	return result

func pose(clip: String, at: float) -> void:
	var players: Array[AnimationPlayer] = []
	if is_instance_valid(actor_player): players.append(actor_player)
	if is_instance_valid(donor_player): players.append(donor_player)
	for player: AnimationPlayer in players:
		player.play(clip, 0.0)
		player.seek(at, true)
		player.advance(0.0)
	if not preview_config.get("equipment_sets",[]).is_empty(): apply_equipment(selected_outfit)

func morph_vertices(node: Node3D) -> PackedVector3Array:
	var result := PackedVector3Array()
	for child: Node in node.find_children("*","MeshInstance3D",true,false):
		var instance := child as MeshInstance3D
		if instance.get_blend_shape_count() == 0: continue
		var mesh := instance.bake_mesh_from_current_blend_shape_mix()
		# Blend-shape bake ignores skinning. Apply actual Skin binds and Skeleton
		# poses: instance.global_transform can count glTF source scales twice.
		var skin_transforms: Array[Transform3D] = []
		if instance.skin!=null:
			var skeleton := instance.get_node(instance.skeleton) as Skeleton3D
			for bind: int in instance.skin.get_bind_count():
				var bone := instance.skin.get_bind_bone(bind)
				if not instance.skin.get_bind_name(bind).is_empty(): bone=skeleton.find_bone(instance.skin.get_bind_name(bind))
				if bone<0:
					fail("Morph skin bind cannot resolve a real bone")
					return result
				skin_transforms.append(skeleton.global_transform*skeleton.get_bone_global_pose(bone)*instance.skin.get_bind_pose(bind))
		for surface: int in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(surface)
			var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var original := instance.mesh.surface_get_arrays(surface)
			for index: int in positions.size():
				if skin_transforms.is_empty():
					result.append(instance.global_transform*positions[index])
				else:
					var point := Vector3.ZERO
					for influence: int in 4:
						var offset := index*4+influence
						point += (skin_transforms[original[Mesh.ARRAY_BONES][offset]]*positions[index])*original[Mesh.ARRAY_WEIGHTS][offset]
					result.append(point)
	return result

func morph_values(node: Node3D) -> Dictionary:
	var values := {}
	for child: Node in node.find_children("*","MeshInstance3D",true,false):
		var instance := child as MeshInstance3D
		for index: int in instance.get_blend_shape_count():
			values[str(instance.name)+":"+str(instance.mesh.get_blend_shape_name(index))] = instance.get_blend_shape_value(index)
	return values

func vertex_distance(first: PackedVector3Array, second: PackedVector3Array) -> float:
	if first.size() != second.size(): return INF
	var distance := 0.0
	for index: int in first.size():
		distance = maxf(distance,first[index].distance_to(second[index]))
	return distance

func capture(filename: String, metadata: Dictionary = {}) -> void:
	for settle: int in 3: await process_frame
	await RenderingServer.frame_post_draw
	if root.get_texture().get_image().save_png(output.path_join(filename)) != OK:
		fail("Cannot save capture: "+filename)
		return
	var camera := root.get_camera_3d()
	shots.append({"file":filename,"camera":{"position":[camera.position.x,camera.position.y,camera.position.z],
		"rotation":[camera.rotation.x,camera.rotation.y,camera.rotation.z],"projection":camera.projection,"size":camera.size,"fov":camera.fov}}.merged(metadata))

func source_views(camera: Camera3D) -> void:
	var saved := camera.global_transform
	var size := camera.size
	pose(preview_config.get("idle_clip","Idle"),0)
	for row: Array in [["front",Vector3(0,0.4,-3.5)],["back",Vector3(0,0.4,3.5)],["left",Vector3(-3.5,0.4,0)]]:
		camera.position = bounds.get_center() + row[1] * bounds.size.length()
		camera.look_at(bounds.get_center())
		await capture(str(row[0])+".png",{"view":row[0]})
	camera.global_transform = saved
	camera.size = size

func face_views(camera: Camera3D) -> void:
	var saved := camera.global_transform
	var size := camera.size
	pose(preview_config.get("idle_clip","Idle"),0)
	for settle: int in 3: await process_frame
	var center := Vector3(0,bounds.get_center().y,0)
	for node: Node in actor.find_children("*","Skeleton3D",true,false):
		var skeleton := node as Skeleton3D
		for index: int in skeleton.get_bone_count():
			if skeleton.get_bone_name(index).ends_with("Head"):
				center = skeleton.global_transform * skeleton.get_bone_global_pose(index).origin
	var offset: Array = preview_config.get("face_center_offset",[0,0.28,-0.15])
	center += Vector3(offset[0],offset[1],offset[2])
	camera.size = float(preview_config.get("face_size_m",0.95))
	camera.position = center + Vector3(0,0,-3)
	camera.look_at(center)
	for node: Node in actor.find_children("*","MeshInstance3D",true,false):
		var mesh := node as MeshInstance3D
		for index: int in mesh.get_blend_shape_count(): mesh.set_blend_shape_value(index,0)
	await capture("face_neutral.png",{"view":"face","weight":0})
	var neutral := morph_vertices(actor)
	for node: Node in actor.find_children("*","MeshInstance3D",true,false):
		var mesh := node as MeshInstance3D
		for index: int in mesh.get_blend_shape_count():
			var name := str(mesh.mesh.get_blend_shape_name(index))
			mesh.set_blend_shape_value(index,1)
			await capture("face_"+name+".png",{"view":"face","morph":name,"weight":1})
			var distance := vertex_distance(neutral,morph_vertices(actor))
			if distance < 0.0001:
				fail("Morph has no actual deformed vertices: "+name)
				return
			morph_checks.append({"mesh":str(mesh.name),"morph":name,"value":mesh.get_blend_shape_value(index),"max_world_delta_m":distance})
			mesh.set_blend_shape_value(index,0)
			for settle: int in 2: await process_frame
	camera.global_transform = saved
	camera.size = size

func finish(camera: Camera3D, skinned: int, tracks: int, extra: Dictionary = {}) -> void:
	if has_failed: return
	var report := {"schema_version":1,"runtime_glb_import":"passed","animation_library_reused":true,
		"animation_library_reloaded_from_disk":true,"motion_libraries":motion_libraries,
		"model":model_path,"animation_donor":donor_path,"bones":skeleton_pose(actor).size(),"skinned_meshes":skinned,
		"resolved_tracks":tracks,"clips":checks,"captures":shots,"segments":segments,"morph_checks":morph_checks,
		"camera_position":[camera.position.x,camera.position.y,camera.position.z],"bounds_method":"baked_skinned_vertices_across_clips",
		"framing_reference":"animation_donor",
		"bounds":{"position":[bounds.position.x,bounds.position.y,bounds.position.z],"size":[bounds.size.x,bounds.size.y,bounds.size.z]},
		"material_mode":material_mode,"mode":preview_config.get("mode","inspection"),"motion_operation":"compatible_rig_reuse",
		"cross_skeleton_retargeting":false,"visual_review":"pending_human"}
	report.merge(extra,true)
	var file := FileAccess.open(output.path_join("preview.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	file.close()
	print("[GAF_CHARACTER_PREVIEW] ",JSON.stringify(report))
	quit(0)

func equipment_node(name: String) -> Node3D:
	var matches := actor.find_children(name,"Node3D",true,false)
	if matches.size()!=1:
		fail("Equipment node must resolve exactly once: "+name)
		return null
	return matches[0] as Node3D

func apply_equipment(index: int) -> Dictionary:
	var sets: Array = preview_config.get("equipment_sets",[])
	if index >= sets.size(): return {}
	selected_outfit = index
	var chosen: Dictionary = sets[index]
	var state := {"set":chosen["name"],"active":chosen["active"],"nodes":{}}
	for entry: Dictionary in preview_config.get("components",[]):
		var node := equipment_node(entry["node"])
		if node==null: return {}
		var active: bool = entry["variant"] in chosen["active"]
		var scale_values: Array = entry["active_scale"]
		var rotation: Array = entry.get("active_rotation",[0,0,0,1])
		node.quaternion = Quaternion(rotation[0],rotation[1],rotation[2],rotation[3]).normalized()
		node.scale = Vector3(scale_values[0],scale_values[1],scale_values[2])
		node.visible = active
		state["nodes"][entry["variant"]] = {"active":active,"visible":node.is_visible_in_tree(),"instance_id":node.get_instance_id(),"scale":[node.scale.x,node.scale.y,node.scale.z]}
	return state

func equipment_geometry(state: Dictionary) -> Dictionary:
	var result := {}
	for entry: Dictionary in preview_config.get("components",[]):
		var node := equipment_node(entry["node"])
		var extent := 0.0
		var visible_meshes := 0
		for child: Node in node.find_children("*","MeshInstance3D",true,false):
			var mesh := child as MeshInstance3D
			if mesh.is_visible_in_tree(): visible_meshes += 1
			var box := mesh.get_aabb()
			for corner: int in 8:
				for other: int in 8:
					extent = maxf(extent,(mesh.global_transform*box.get_endpoint(corner)).distance_to(mesh.global_transform*box.get_endpoint(other)))
		var active: bool = entry["variant"] in state.get("active",[])
		if extent<0.02 or (active and visible_meshes==0) or (not active and visible_meshes!=0):
			fail("Equipment geometry/visibility is inconsistent after real animation: "+entry["variant"])
		result[entry["variant"]] = {"world_extent_m":extent,"visible_meshes":visible_meshes,"active":active}
	return result

func input_setup() -> void:
	for pair: Array in [["gaf_left",KEY_A],["gaf_right",KEY_D],["gaf_forward",KEY_W],["gaf_back",KEY_S],["gaf_attack",KEY_SPACE],["gaf_equip1",KEY_1],["gaf_equip2",KEY_2]]:
		if not InputMap.has_action(pair[0]): InputMap.add_action(pair[0])
		var event := InputEventKey.new()
		event.physical_keycode = pair[1]
		InputMap.action_add_event(pair[0],event)
	var mouse := InputEventMouseButton.new()
	mouse.button_index = MOUSE_BUTTON_LEFT
	InputMap.action_add_event("gaf_attack",mouse)

func key_event(keycode: int, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = pressed
	Input.parse_input_event(event)

func actor_ids(type_name: String, skinned_only: bool = false) -> Array:
	var ids: Array = []
	for node: Node in actor.find_children("*",type_name,true,false):
		if skinned_only and (node as MeshInstance3D).skin==null: continue
		ids.append(node.get_instance_id())
	return ids

func movement_preview(camera: Camera3D, interactive: bool) -> Dictionary:
	input_setup()
	var controller := Node3D.new()
	controller.name = "GAF_PreviewMotion"
	world.add_child(controller)
	actor.reparent(controller,true)
	var body_ids := actor_ids("MeshInstance3D",true)
	var rig_ids := actor_ids("Skeleton3D")
	var floor_node := world.get_node("GAF_Floor") as Node3D
	floor_node.position.y = -0.02
	var grid := MeshInstance3D.new()
	var lines := ImmediateMesh.new()
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color("55636b")
	lines.surface_begin(Mesh.PRIMITIVE_LINES,material)
	for step: int in range(-12,13):
		lines.surface_add_vertex(Vector3(step,-0.018,-12)); lines.surface_add_vertex(Vector3(step,-0.018,12))
		lines.surface_add_vertex(Vector3(-12,-0.018,step)); lines.surface_add_vertex(Vector3(12,-0.018,step))
	lines.surface_end()
	grid.mesh = lines
	world.add_child(grid)
	var hud := Label.new()
	hud.position = Vector2(18,18)
	hud.add_theme_font_size_override("font_size",19)
	root.add_child(hud)
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 55
	var states: Array[Dictionary] = []
	var outfit_index := 0
	var outfit := apply_equipment(0)
	states.append(outfit)
	var events := {30:[[KEY_W,true]],90:[[KEY_W,false],[KEY_SPACE,true]],91:[[KEY_SPACE,false]],140:[[KEY_2,true]],141:[[KEY_2,false]],160:[[KEY_W,true],[KEY_D,true]],220:[[KEY_W,false],[KEY_D,false],[KEY_SPACE,true]],221:[[KEY_SPACE,false]],280:[[KEY_1,true]],281:[[KEY_1,false]]}
	var frame := 0
	var current := ""
	var clip_time := 0.0
	var attack_left := 0.0
	var attacks := 0
	var distance := 0.0
	var used_clips: Dictionary = {}
	var attack_origins: Dictionary = {}
	var equipment_attack_travel := 0.0
	var geometry_checks: Array[Dictionary] = []
	root.close_requested.connect(func() -> void: interactive_exit=true)
	auto_accept_quit = false
	while (interactive and not interactive_exit and not Input.is_key_pressed(KEY_ESCAPE)) or (not interactive and frame<310):
		var dt := minf(root.get_process_delta_time(),0.05) if interactive else 1.0/30.0
		if not interactive and events.has(frame):
			for row: Array in events[frame]: key_event(row[0],row[1])
		if Input.is_action_just_pressed("gaf_equip1") or Input.is_action_just_pressed("gaf_equip2"):
			outfit_index = 1 if Input.is_action_just_pressed("gaf_equip2") else 0
			outfit = apply_equipment(outfit_index)
			states.append(outfit)
		var direction2 := Input.get_vector("gaf_left","gaf_right","gaf_forward","gaf_back")
		var direction := Vector3(direction2.x,0,direction2.y)
		if Input.is_action_just_pressed("gaf_attack") and attack_left<=0:
			attacks += 1
			attack_left = actor_player.get_animation(preview_config.get("attack_clip","Punch")).length
			attack_origins.clear()
		var attacking := attack_left>0
		var next: String = preview_config.get("attack_clip","Punch") if attacking else preview_config.get("walk_clip","Walk") if direction.length()>0 else preview_config.get("idle_clip","Idle")
		if next!=current:
			current = next; clip_time = 0
		used_clips[current] = true
		if not attacking and direction.length()>0:
			var previous := controller.position
			controller.position += direction * float(preview_config.get("walk_speed_mps",1.0)) * dt
			controller.rotation.y = atan2(-direction.x,-direction.z)
			distance += controller.position.distance_to(previous)
		pose(current,minf(clip_time,actor_player.get_animation(current).length) if attacking else fmod(clip_time,actor_player.get_animation(current).length))
		clip_time += dt
		attack_left -= dt
		camera.position = controller.position + Vector3(0,1.5,3.4)
		camera.look_at(controller.position+Vector3(0,0.95,0))
		hud.text = "Game Asset Factory | third-person asset preview\nWASD move   Space / LMB attack   1 / 2 equipment   Esc close\n"+current+" | "+str(outfit.get("set","none"))
		await process_frame
		await RenderingServer.frame_post_draw
		if attacking:
			for component: Dictionary in preview_config.get("components",[]):
				if component["variant"] not in outfit.get("active",[]): continue
				var node := equipment_node(component["node"])
				var point := controller.global_transform.affine_inverse() * node.global_position
				if not attack_origins.has(component["node"]): attack_origins[component["node"]] = point
				equipment_attack_travel = maxf(equipment_attack_travel,point.distance_to(attack_origins[component["node"]]))
		if not interactive and frame in [5,60,110,150,190,240,300]:
			geometry_checks.append({"frame":frame,"equipment":equipment_geometry(outfit)})
			await capture("third_person_%03d.png"%frame,{"view":"third_person","clip":current,"equipment":outfit.get("set","none")})
		frame += 1
	if has_failed: return {}
	for key: int in [KEY_W,KEY_A,KEY_S,KEY_D,KEY_SPACE,KEY_1,KEY_2]: key_event(key,false)
	var unchanged: bool = body_ids==actor_ids("MeshInstance3D",true) and rig_ids==actor_ids("Skeleton3D")
	if not interactive and (distance<1.0 or attacks<2 or states.size()<3 or not unchanged or equipment_attack_travel<0.005):
		fail("Third-person input/movement/equipment proof failed")
		return {}
	for clip: String in used_clips: checks.append({"clip":clip,"played_by_input_controller":true})
	return {"scripted_input":not interactive,"input_api":"Input.parse_input_event / InputMap","frames":frame,"distance_m":distance,"attacks":attacks,"equipment_states":states,"geometry_checks":geometry_checks,"body_and_skeleton_instance_ids_unchanged":unchanged,"equipment_relative_attack_motion_m":equipment_attack_travel,"camera_follows_translation":true,"camera_rotates_with_actor":false,"physics_collision_tested":false}

func percentile(values: Array[float], fraction: float) -> float:
	var ordered := values.duplicate()
	ordered.sort()
	return ordered[int(floor((ordered.size()-1)*fraction))]

func performance_preview(camera: Camera3D) -> Dictionary:
	donor.queue_free()
	await process_frame
	await process_frame
	apply_equipment(0)
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.position = Vector3(0,1.5,3.4)
	camera.look_at(Vector3(0,0.95,0))
	var warmup: int = preview_config.get("warmup_frames",120)
	var count: int = preview_config.get("sample_frames",600)
	var frame_times: Array[float] = []
	var process_times: Array[float] = []
	var max_calls := 0
	var max_primitives := 0
	var max_vram := 0
	var max_static := 0
	var clip: String = preview_config.get("walk_clip","Walk")
	var start := Time.get_ticks_usec()
	var previous := start
	var sample_start := 0
	var draw_start := 0
	var frame := 0
	while frame_times.size()<count or sample_start==0 or Time.get_ticks_usec()-sample_start<3000000:
		pose(clip,fmod(float(Time.get_ticks_usec()-start)/1000000.0,actor_player.get_animation(clip).length))
		await process_frame
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		if frame>=warmup and now-start>=1200000:
			if sample_start==0:
				sample_start=now
				draw_start=Engine.get_frames_drawn()
			frame_times.append(float(now-previous)/1000.0)
			process_times.append(Performance.get_monitor(Performance.TIME_PROCESS)*1000.0)
			max_calls = maxi(max_calls,int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
			max_primitives = maxi(max_primitives,int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)))
			max_vram = maxi(max_vram,int(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)))
			max_static = maxi(max_static,int(Performance.get_monitor(Performance.MEMORY_STATIC)))
		previous = now
		frame += 1
	var budget: float = preview_config.get("p95_frame_budget_ms",16.667)
	var result := {"warmup_frames_minimum":warmup,"sample_frames_requested":count,"sample_frames":frame_times.size(),"sample_seconds":float(Time.get_ticks_usec()-sample_start)/1000000.0,"fixed_fps":false,"movie_capture":false,"gpu_readback_during_measurement":false,
		"frame_wall_ms_p50":percentile(frame_times,0.5),"frame_wall_ms_p95":percentile(frame_times,0.95),"frame_wall_ms_max":frame_times.max(),
		"godot_process_ms_p95":percentile(process_times,0.95),"max_draw_calls":max_calls,"max_primitives":max_primitives,
		"max_video_memory_bytes":max_vram,"max_godot_static_memory_bytes":max_static,"visible_actors":1,"reference_actor_removed":true,
		"cpu":OS.get_processor_name(),"gpu":RenderingServer.get_video_adapter_name(),"godot":Engine.get_version_info().string,
		"renderer":RenderingServer.get_current_rendering_method(),"viewport":[root.size.x,root.size.y],
		"p95_frame_budget_ms":budget,"budget_passed":percentile(frame_times,0.95)<=budget}
	result["rendered_frames_during_sampling"] = Engine.get_frames_drawn()-draw_start
	var file := FileAccess.open(output.path_join("performance.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"\t"));file.close()
	checks.append({"clip":clip,"performance_sampled":true})
	if not result["budget_passed"]:
		fail("Performance exceeded configured frame budget; measurements retained")
	return result

func _run() -> void:
	if donor_path.is_empty(): donor_path = model_path
	actor = load_actor(model_path)
	donor = load_actor(donor_path)
	if actor == null or donor == null:
		fail("Cannot load actor/donor GLB")
		return
	world = Node3D.new()
	root.add_child(world)
	world.add_child(actor)
	world.add_child(donor)
	donor.visible = false
	actor_player = player_for(actor)
	donor_player = player_for(donor)
	if actor_player == null or donor_player == null:
		fail("No real AnimationPlayer")
		return
	actor_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	donor_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	# Replace the variant's libraries with the baseline libraries, not just its clip names.
	for library: StringName in actor_player.get_animation_library_list():
		actor_player.remove_animation_library(library)
	for library: StringName in donor_player.get_animation_library_list():
		var filename := "motions_" + ("default" if str(library).is_empty() else str(library).replace("/","_")) + ".tres"
		var library_path := output.path_join(filename)
		if ResourceSaver.save(donor_player.get_animation_library(library).duplicate(true),library_path) != OK:
			fail("Cannot save reusable motion library")
			return
		var loaded := ResourceLoader.load(library_path,"AnimationLibrary",ResourceLoader.CACHE_MODE_IGNORE) as AnimationLibrary
		if loaded == null:
			fail("Cannot reload reusable motion library")
			return
		actor_player.add_animation_library(library,loaded)
		motion_libraries.append(filename)
	var clips: Array[String] = []
	var track_count := 0
	for clip: String in actor_player.get_animation_list():
		if clip == "RESET": continue
		clips.append(clip)
		var animation := actor_player.get_animation(clip)
		var base := actor_player.get_node(actor_player.root_node)
		for track: int in animation.get_track_count():
			var path := animation.track_get_path(track)
			var target := base.get_node_or_null(NodePath(path.get_concatenated_names()))
			if target == null:
				fail("Donor track cannot resolve on variant: " + str(path))
				return
			if target is Skeleton3D and path.get_subname_count() > 0:
				if (target as Skeleton3D).find_bone(path.get_subname(0)) < 0:
					fail("Donor bone track missing on variant")
					return
			track_count += 1
	if clips.is_empty() or skeleton_pose(actor).is_empty():
		fail("No bone animation clips")
		return
	var first := true
	var skinned := 0
	for child: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var instance := child as MeshInstance3D
		if instance.skin != null: skinned += 1
		if material_mode == "clay":
			var clay := StandardMaterial3D.new()
			clay.albedo_color = Color("888f91")
			clay.roughness = 0.82
			instance.material_override = clay
		var box := instance.get_aabb()
		for corner: int in 8:
			var point := instance.global_transform * box.get_endpoint(corner)
			if first:
				bounds = AABB(point, Vector3.ZERO)
				first = false
			else: bounds = bounds.expand(point)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("253039")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("bec9cf")
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.environment = env
	world.add_child(environment)
	for entry: Array in [[Vector3(-40,-35,0),1.0],[Vector3(-25,140,0),0.6]]:
		var light := DirectionalLight3D.new()
		light.rotation_degrees = entry[0]
		light.light_energy = entry[1]
		light.shadow_enabled = true
		world.add_child(light)
	var floor_node := MeshInstance3D.new()
	floor_node.name = "GAF_Floor"
	var plane := PlaneMesh.new()
	plane.size = Vector2(30,30)
	floor_node.mesh = plane
	floor_node.position.y = bounds.position.y - 0.03
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("3d464d")
	floor_material.roughness = 0.9
	floor_node.material_override = floor_material
	world.add_child(floor_node)
	var camera := Camera3D.new()
	camera.current = true
	camera.near = 0.01
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = maxf(bounds.size.y,maxf(bounds.size.x,bounds.size.z)) * 1.25
	camera.position = bounds.get_center() + Vector3(-2.5,1.2,-3.5) * bounds.size.length()
	world.add_child(camera)
	camera.look_at(bounds.get_center())
	root.size = Vector2i(960,720)
	# Imported skin bounds may be in bind coordinates and cannot frame a posed actor.
	# Preflight real skinned positions over each clip, then lock one camera for all clips.
	camera.size = 3.0
	camera.position = Vector3(-3,2,-4)
	camera.look_at(Vector3(0,0.5,0))
	var first_skinned := true
	for clip: String in clips:
		var length := actor_player.get_animation(clip).length
		for sample: int in 3:
			pose(clip,length * float(sample) * 0.4)
			for settle: int in 3: await process_frame
			await RenderingServer.frame_post_draw
			# Match before/after framing to the unedited donor, even when a local
			# shape edit changes the actor's maximum extent. No camera-fit drift.
			for point: Vector3 in baked_vertices(donor):
				if first_skinned:
					bounds = AABB(point,Vector3.ZERO)
					first_skinned = false
				else: bounds = bounds.expand(point)
	if first_skinned or bounds.size.length() < 0.001:
		fail("No actual skinned bounds")
		return
	floor_node.position.y = bounds.position.y - 0.03
	camera.size = maxf(bounds.size.y,maxf(bounds.size.x,bounds.size.z)) * 1.3
	camera.position = bounds.get_center() + Vector3(-2.5,1.2,-3.5) * bounds.size.length()
	camera.look_at(bounds.get_center())
	if preview_config.get("capture_views",false): await source_views(camera)
	if preview_config.get("capture_morphs",false): await face_views(camera)
	if has_failed: return
	var mode: String = preview_config.get("mode","inspection")
	if mode in ["third_person","interactive"]:
		var movement: Dictionary = await movement_preview(camera,mode=="interactive")
		finish(camera,skinned,track_count,{"movement":movement})
		return
	if mode=="performance":
		var performance: Dictionary = await performance_preview(camera)
		finish(camera,skinned,track_count,{"performance":performance})
		return
	for clip: String in clips:
		var duration := actor_player.get_animation(clip).length
		var rest_pose := {}
		var rest_vertices := PackedVector3Array()
		var bone_travel := 0.0
		var vertex_travel := 0.0
		var donor_error := 0.0
		var morph_travel := 0.0
		var morph_value_error := 0.0
		var rest_morph := PackedVector3Array()
		for sample: int in 3:
			var at := duration * float(sample) * 0.4
			pose(clip,at)
			for settle: int in 3: await process_frame
			await RenderingServer.frame_post_draw
			var current_pose := skeleton_pose(actor)
			var vertices := baked_vertices(actor)
			var deformed := morph_vertices(actor)
			var actor_values := morph_values(actor)
			var donor_values := morph_values(donor)
			if actor_values.keys()!=donor_values.keys():
				fail("Donor morph track bindings differ")
				return
			for key: String in actor_values:
				morph_value_error=maxf(morph_value_error,absf(actor_values[key]-donor_values[key]))
			donor_error = maxf(donor_error,pose_distance(current_pose,skeleton_pose(donor)))
			if sample == 0:
				rest_pose = current_pose
				rest_vertices = vertices
				rest_morph = deformed
			else:
				bone_travel = maxf(bone_travel,pose_distance(rest_pose,current_pose))
				morph_travel = maxf(morph_travel,vertex_distance(rest_morph,deformed))
				if rest_vertices.size() != vertices.size():
					fail("Skinned topology changed during playback")
					return
				for index: int in vertices.size():
					vertex_travel = maxf(vertex_travel,vertices[index].distance_to(rest_vertices[index]))
			var filename := "clip_" + clip.replace("/","_").replace(":","_") + "_" + str(sample) + ".png"
			if root.get_texture().get_image().save_png(output.path_join(filename)) != OK:
				fail("Cannot capture animation frame")
				return
			shots.append({"file":filename,"clip":clip,"time":at})
		var declared_static: bool = clip in preview_config.get("static_pose_actions", [])
		var morph_only: bool = clip in preview_config.get("morph_only_actions", [])
		if (not declared_static and not morph_only and (bone_travel < 0.01 or vertex_travel < 0.0001)) or (morph_only and morph_travel < 0.0001) or donor_error > 0.002 or morph_value_error>0.0001:
			fail("Bone/skinned motion or donor agreement failed: " + str([clip,bone_travel,vertex_travel,donor_error]))
			return
		checks.append({"clip":clip,"duration":duration,"bone_motion_radians":bone_travel,"skinned_vertex_motion_m":vertex_travel,"morph_vertex_motion_m":morph_travel,"morph_only":morph_only,"donor_morph_weight_error":morph_value_error,"donor_pose_error_radians":donor_error,"baked_vertices":rest_vertices.size(),"declared_static_pose":declared_static})
		var start_frame := Engine.get_frames_drawn()
		for frame: int in maxi(2,int(ceil(duration*2.0*30.0))):
			pose(clip,fmod(float(frame)/30.0,duration))
			await process_frame
			await RenderingServer.frame_post_draw
		segments.append({"clip":clip,"first_engine_frame":start_frame,"last_engine_frame":Engine.get_frames_drawn(),"camera_moved":false})
	finish(camera,skinned,track_count)
