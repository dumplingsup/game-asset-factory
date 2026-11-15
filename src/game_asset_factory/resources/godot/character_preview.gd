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

func _initialize() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--model="): model_path = argument.trim_prefix("--model=")
		if argument.begins_with("--donor="): donor_path = argument.trim_prefix("--donor=")
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		if argument.begins_with("--material-mode="): material_mode = argument.trim_prefix("--material-mode=")
	_run.call_deferred()

func fail(message: String) -> void:
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
	for player: AnimationPlayer in [actor_player, donor_player]:
		player.play(clip, 0.0)
		player.seek(at, true)
		player.advance(0.0)

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
			for point: Vector3 in baked_vertices(actor):
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
	for clip: String in clips:
		var duration := actor_player.get_animation(clip).length
		var rest_pose := {}
		var rest_vertices := PackedVector3Array()
		var bone_travel := 0.0
		var vertex_travel := 0.0
		var donor_error := 0.0
		for sample: int in 3:
			var at := duration * float(sample) * 0.4
			pose(clip,at)
			for settle: int in 3: await process_frame
			await RenderingServer.frame_post_draw
			var current_pose := skeleton_pose(actor)
			var vertices := baked_vertices(actor)
			donor_error = maxf(donor_error,pose_distance(current_pose,skeleton_pose(donor)))
			if sample == 0:
				rest_pose = current_pose
				rest_vertices = vertices
			else:
				bone_travel = maxf(bone_travel,pose_distance(rest_pose,current_pose))
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
		if bone_travel < 0.01 or vertex_travel < 0.0001 or donor_error > 0.002:
			fail("Bone/skinned motion or donor agreement failed: " + str([clip,bone_travel,vertex_travel,donor_error]))
			return
		checks.append({"clip":clip,"duration":duration,"bone_motion_radians":bone_travel,"skinned_vertex_motion_m":vertex_travel,"donor_pose_error_radians":donor_error,"baked_vertices":rest_vertices.size()})
		var start_frame := Engine.get_frames_drawn()
		for frame: int in maxi(2,int(ceil(duration*2.0*30.0))):
			pose(clip,fmod(float(frame)/30.0,duration))
			await process_frame
			await RenderingServer.frame_post_draw
		segments.append({"clip":clip,"first_engine_frame":start_frame,"last_engine_frame":Engine.get_frames_drawn(),"camera_moved":false})
	var report := {"schema_version":1,"runtime_glb_import":"passed","animation_library_reused":true,
		"animation_library_reloaded_from_disk":true,"motion_libraries":motion_libraries,
		"model":model_path,"animation_donor":donor_path,"bones":skeleton_pose(actor).size(),"skinned_meshes":skinned,
		"resolved_tracks":track_count,"clips":checks,"captures":shots,"segments":segments,
		"camera_position":[camera.position.x,camera.position.y,camera.position.z],"bounds_method":"baked_skinned_vertices_across_clips",
		"bounds":{"position":[bounds.position.x,bounds.position.y,bounds.position.z],"size":[bounds.size.x,bounds.size.y,bounds.size.z]},
		"material_mode":material_mode,"visual_review":"pending_human"}
	var file := FileAccess.open(output.path_join("preview.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	file.close()
	print("[GAF_CHARACTER_PREVIEW] ",JSON.stringify(report))
	quit(0)
